#!/usr/bin/env python3
import os
import sys

import firebase_admin
from firebase_admin import credentials, firestore
import argparse
import json
import redis
import ast

from google.cloud.firestore_v1 import CollectionReference
from redis import DataError


class DataMigration:
    """
    CLI for importing/exporting data in Cloud Firebase and redis

    Usage:
    -f/--file : import mode: specify .json file to import into database (must be formatted with collection name as top level keys)
                export mode: specify .json file to export data into
    -c/--collections : collection(s) to import into/export from database
    -d/--documents : document(s) to import/export
    -i/--import_db : import only mode
    -e/--export_db : export only mode
    -o/--overwrite : allow import to overwrite existing documents/collections
    -u/--datastore : datastore (firestore [default] or redis)

    TODO:
        - Update credentials when switching GCP projects
        - Formatting of nested data structures
        - get collections by prefix
        - Improve redis type-handling
        - deal with hset() redis-py issue

    NOTE: redis-py currently has a bug with hset(), where a dict cannot be successfully passed. Until this issue is fixed,
    the encode() method in connections.py must be updated with this conditional:
                                elif isinstance(value, dict):
                                    value = str(value).encode()

    @author Arjun Srivastava
    """

    def __init__(self, cred: credentials.Certificate = None):
        self.parser = argparse.ArgumentParser(prog='data_migration',
                                              description='Import/export data between datastores (Firestore, redis')
        self._setup_parser()
        self.args = self.parser.parse_args()

        self.cred = cred
        self.collections, self.documents = [], []
        self.json_map, self.export_file = None, None
        self.exported_map = {}
        self.datastore = 'firestore'
        self._set_args()

        if self.datastore == 'firestore':
            if credentials:
                firebase_admin.initialize_app(self.cred)

            # Initialize client
            self.db = firestore.client()

        elif self.datastore == 'redis':
            redis_host = input('Please enter the redis host address: ').strip()
            self.r = redis.Redis(host=redis_host, decode_responses=True)
            # For hardcoding address
            # self.r = redis.Redis(host='', decode_responses=True)
        else:
            print('Please enter a valid datastore for the script to use (firestore or redis)')
            sys.exit(1)

        # Import from file
        self.import_file()

        # Export to file
        self.export_to_file()

    def _setup_parser(self):
        self.parser.add_argument('-c', '--collections', nargs='*', help='the collections to be exported from/imported '
                                                                        'into')
        self.parser.add_argument('-f', '--file', help='file to read json data from')
        self.parser.add_argument('-i', '--import_db', action='store_true', help='import into database')
        self.parser.add_argument('-e', '--export_db', action='store_true', help='export from database')
        self.parser.add_argument('-o', '--overwrite', action='store_true', help='overwrite existing collections')
        self.parser.add_argument('-d', '--documents', nargs='*', help='specific documents to export/import')
        self.parser.add_argument('-u', '--datastore', help='Datastore to use script with (firestore or redis)')

    def _set_args(self):
        self.collections = self.args.collections
        self.documents = self.args.documents
        self.datastore = self.args.datastore if self.args.datastore is not None else 'firestore'
        if self.args.import_db:
            self.json_map = self.get_json(self.args.file) if self.args.file is not None else None
        elif self.args.export_db:
            self.export_file = self.args.file if self.args.file is not None else None

    def get_collection(self, target: str):
        if self.datastore == 'firestore':
            if not self._collection_exists(target, self.db.collections):
                if self.args.import_db:
                    print("Target collection, \"" + target + "\" doesn't exist. Creating new collection.")
                elif self.args.export_db:
                    print("Target collection, \"" + target + "\" doesn't exist. Cannot export")
                    return None
            return self.db.collection(target)
        elif self.datastore == 'redis':
            if not self.r.exists(target):
                if self.args.import_db:
                    print("Target key, \"" + target + "\" doesn't exist. Key will be created.")
                elif self.args.export_db:
                    print("Target key, \"" + target + "\" doesn't exist. Cannot export")
                    return None
            return self.r.keys(target)

    def _do_collections_import(self, collection: str):
        print(f'Importing file into {collection}...')
        if collection in self.json_map.keys():
            file_data = self.json_map.get(collection)
        else:
            print('Make sure collection/key names are at the top level of the .json file...')
            sys.exit(1)
        col = self.get_collection(collection)
        if self.datastore == 'firestore':
            self._do_firestore_import(collection, col, file_data)
        elif self.datastore == 'redis':
            if self.r.exists(collection):
                if self.args.overwrite:
                    print(f'Overwriting existing key: {collection}')
                    self._do_redis_import(collection, file_data)
                else:
                    print(f'Cannot overwrite existing key: {collection}. Please run again with -o flag to '
                          f'overwrite')
            else:
                self._do_redis_import(collection, file_data)


    def _do_collections_export(self, collection: str):
        print(f'Exporting collection: {collection}')
        col = self.get_collection(collection)
        if col is not None:
            if self.datastore == 'firestore':
                doc_to_data = {}
                self._do_firestore_export(doc_to_data, col, 0)
                self.exported_map[collection] = doc_to_data
            elif self.datastore == 'redis':
                self._do_redis_export(collection, col)

    def _do_firestore_import(self, collection_name: str, col, file_data):
        for doc in file_data.keys():
            if self.documents is None or len(self.documents) == 0 or doc in self.documents:
                db_document = col.document(doc)
                data = file_data.get(doc)
                if self._document_exists(doc, col):
                    if not self.args.overwrite:
                        print(f'Cannot overwrite existing document: {doc}. Please run again with -o flag to '
                              f'overwrite')
                    else:
                        print(f'Updating document: {doc}')
                        db_document.update(data)
                else:
                    print(f'Creating new document: {doc}')
                    db_document.set(data)
        print(f'Import finished for collection: {collection_name}')

    def _do_firestore_export(self, doc_to_data: dict, collection, count, limit=500, cursor=None):
        while True:
            docs = []  # Frees the memory incurred in the recursion algorithm.
            if cursor:
                docs = [snapshot for snapshot in
                        collection.limit(limit).order_by('__name__').start_after(cursor).stream()]
            else:
                docs = [snapshot for snapshot in collection.limit(limit).order_by('__name__').stream()]

            for doc in docs:
                if self.documents is None or len(self.documents) == 0 or doc.id in self.documents:
                    print(f'Exporting document: {doc.id}')
                    doc_data = doc.to_dict()
                    doc_to_data[doc.id] = doc_data
                count += 1

            if len(docs) == limit:
                cursor = docs[limit - 1]
                continue

            break

    def _do_redis_import(self, collection_name: str, file_data):
        # Different actions based on redis data type
        if isinstance(file_data, dict):  # Hash
            if self.documents is None or len(self.documents) == 0:
                # redis 3.5.1: error using hset() to push dict to hash
                try:
                    self.r.hset(collection_name, mapping=file_data)
                except DataError:
                    print("Current issue with redis-py, cannot import dictionary into hash, see NOTE...")
            else:
                doc_data = {}
                for doc in file_data.keys():
                    if doc in self.documents:
                        doc_data[doc] = file_data[doc]
                # redis 3.5.1: error using hset() to push dict to hash
                try:
                    self.r.hset(collection_name, mapping=doc_data)
                except DataError:
                    print("Current issue with redis-py, cannot import dictionary into hash, see NOTE...")
        elif isinstance(file_data, str):  # String, List, or Set
            # Not robust
            if file_data.startswith("{"):  # Set
                self.r.sadd(collection_name, file_data)
            elif file_data.startswith("["):  # List
                self.r.lpush(collection_name, file_data)
            else:
                self.r.append(collection_name, file_data)  # String
        print(f'Import finished for key: {collection_name}')

    def _do_redis_export(self, collection_name: str, col):
        data_key = col.pop()
        val = self._get_redis_val(data_key)
        data_type = self.r.type(data_key)
        # Different actions based on redis data type
        if data_type == 'hash':
            doc_to_data = {}
            for doc in val.keys():
                if self.documents is None or len(self.documents) == 0 or doc in self.documents:
                    print(f'Exporting document: {doc}')
                    # Transform string to dictionary
                    dict_data = ast.literal_eval(val[doc])
                    doc_to_data[doc] = dict_data
            self.exported_map[collection_name] = doc_to_data
        elif data_type == 'string':
            self.exported_map[collection_name] = val
        elif data_type == 'list':
            self.exported_map[collection_name] = val
        elif data_type == 'set':
            self.exported_map[collection_name] = val

    def import_file(self):
        if self.args.import_db and self.json_map is not None:
            if self.collections is not None:
                print('Importing specific collections')
                for col in self.collections:
                    self._do_collections_import(col)
            else:
                print('Importing entire file')
                for col in self.json_map.keys():
                    self._do_collections_import(col)

    def export_to_file(self):
        if self.args.export_db and self.export_file is not None:
            if self.collections is not None:
                print('Exporting specific collections')
                for col in self.collections:
                    self._do_collections_export(col)
            else:
                print('Exporting all collections')
                if self.datastore == 'firestore':
                    for col in self.db.collections():
                        self._do_collections_export(col.id)
                elif self.datastore == 'redis':
                    for col in self.r.scan_iter():
                        self._do_collections_export(col)
            self._dict_to_json(self.exported_map, self.export_file)

    def _get_redis_val(self, data_key):
        key_type = self.r.type(data_key)
        if key_type == 'hash':
            return self.r.hgetall(data_key)
        elif key_type == 'string':
            return self.r.get(data_key)
        elif key_type == 'set':
            return self.r.smembers(data_key)
        elif key_type == 'list':
            return self.r.lrange(data_key, 0, -1)

    @staticmethod
    def get_json(json_path: str) -> dict:
        if os.path.isfile(json_path):
            with open(json_path, 'r') as json_data:
                text_data = json_data.read().strip()
                if text_data[0] != '{' or text_data[-1] != '}':
                    print('bad json')
                data = json.loads(text_data)
                return data
        else:
            print('Invalid file name or path!')
            sys.exit(1)

    @staticmethod
    def _document_exists(document: str, collection: CollectionReference) -> bool:
        return collection.document(document).get().exists

    @staticmethod
    def _collection_exists(target, collections) -> bool:
        return target in [collection.id for collection in collections()]

    @staticmethod
    def _dict_to_json(d: dict, file):
        with open(file, 'w') as fp:
            json.dump(d, fp, indent=4, default=str)

    @staticmethod
    def filter_by_keyword(string: str, keyword: str):
        return string.startswith(keyword)


if __name__ == '__main__':
    # Path to credentials
    key = credentials.Certificate("stg_credentials.json")
    tool = DataMigration(key)
