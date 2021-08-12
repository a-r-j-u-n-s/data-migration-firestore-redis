# Data Migration CLI

Guide to using the standalone *data_migration* bash/python CLI. This script is intended to be used for GCP (Cloud Firebase) or redis.
### Features
- Data migration between GCP Firestore environments without using buckets
- Type-aware redis export/import
- Export/import with Firestore and redis and local .json

## Description
There are 3 primary use cases for this CLI:

1. **Export/Import**
   1. import/export data from environment_one <-> environment_two (vice versa)
      1. e.g. dev → stage
   2. import/export between redis hosts
2. **Export**
   1. Export specific collections/documents from Firestore project to a .json file
   2. Export specific keys from redis to a .json file
   3. Export all Firestore/redis data to .json file
3. **Import**
   1. Import specific collections/documents from .json file into Firestore project
   2. Import specific keys/values from .json file into redis
   3. Import all Firestore data from .json file

## Usage
There are 2 files that can be run from the command line:
1. data_migration.py
2. **data_migration.sh** (*intended*)

*The bash script is the intended use, the user can run the python script independently if desired

```./data_migration.sh [-f JSON FILE] [-c COLLECTIONS] [-d DOCUMENTS] [-i IMPORT] [-e EXPORT] [-o OVERWRITE] [-ds DATASTORE]```

 -f/--file : 
 - import mode: specify .json file to import into database (must be formatted with collection name as top level keys)
 - export mode: specify .json file to export data into

 -c/--collections [optional] : 
 - specific collection(s) to import into/export from database

 -d/--documents [optional] :
 - specific document(s) to import/export

 -i/--import_db :
 - import only mode

 -e/--export_db :
 - export only mode

 -o/--overwrite [optional] :
 - allow import to overwrite existing documents/collections

 -u/--datastore :
- Select datastore for script to use
- firestore or redis

### Executing script

* Script can be run either in **import** mode, **export** mode, or combined **export/import** mode
  * *For combined export/import, run script with both flags:* -e -i
  * Combined export/import can only be run for one datastore at a time
  #### Example: Combined Export/Import for Firestore
     ```
     ./data_migration.sh -c example_collection1 example_collection2 -f test.json -u firestore -o -e -i
     ```
    - Prompt the user for the project ID of the GCP project to export from, then switch to that environment
    - Export *example_collection1* and *example_collection2* to "test.json"
    - Prompt user for project ID to import into, then switch to that environment
    - Import contents of "test.json" into the Firestore environment, overwriting the two collections if they already exist (due to the -o flag being set)
    
  #### Example: Combined Export/Import for redis
     ```
     ./data_migration.sh -c example_key1 example_key2 -f test.json -u redis -e -i
     ```
    - Prompt the user for redis host to export from
    - Export *example_key1* and *example_key2* to "test.json" 
    - Prompt user for redis host to import into
    - Import keys in "test.json" to redis

### Data Format (Firestore)
- All JSON data will be exported in this format. If a user wants to import a custom JSON file, it must follow this format as well:
```json lines
{
  "example_collection1": {  // collection/key names as top level keys
    "test_document1": {   // documents/values nested in collection as dictionaries or strings
    },
    "test_document2": {
      "test": "data"
    }
  },
  "example_collection2": {
    "test_document3": {
      "test": "also data"
    }
  }
}
```

### Data Format (redis)
- Different redis data types must be represented differently in the JSON
- This script currently handles hashes, strings, and sets
```json lines
{
    "string_key": "string_data",  // How to represent STRING
    "set_key": "{'data', 'more data', 'some other data'}",  // How to represent SET
    "hash_key": {   // How to represent HASH
        "document1": {
            "key1": "data",
            "key2": "914123",
            "key3": "9",
            "key4": "11",
            "key5": "test data",
            "to_category_id": "789"
        },
        "document2": {
            "key8": "value",
            "key7": "1234567"
        }
    }
}
```

## Issues
- Currently, an issue exists with redis-py
  - Unable to import dictionaries into hash with hset()
  - Issue has been opened in redis-py

## Authors

Arjun Srivastava
