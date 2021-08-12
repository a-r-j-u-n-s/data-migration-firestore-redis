#!/bin/bash
# Script for import/export in Cloud Firestore
# Author: Arjun Srivastava

# Import/Export flags
import_db='false'
export_db='false'
overwrite='false'

while getopts f:c:d:u:ieo flag
do
    case "${flag}" in
        f) file=${OPTARG};;
        u) datastore=${OPTARG};;
        c)  collections=("$OPTARG")
            until [[ $(eval "echo \${$OPTIND}") =~ ^-.* ]] || [ -z "$(eval "echo \${$OPTIND}")" ]; do
                collections+=("$(eval "echo \${$OPTIND}")")
                OPTIND=$((OPTIND + 1))
            done
            ;;
        d) documents=("$OPTARG")
          until [[ $(eval "echo \${$OPTIND}") =~ ^-.* ]] || [ -z "$(eval "echo \${$OPTIND}")" ]; do
                documents+=("$(eval "echo \${$OPTIND}")")
                OPTIND=$((OPTIND + 1))
            done
            ;;
        i) import_db='true';;
        e) export_db='true';;
        o) overwrite='true';;
        *) echo "usage: $0 [-f JSON FILE] [-c COLLECTIONS] [-d DOCUMENTS] [-i IMPORT] [-e EXPORT] [-o OVERWRITE] [-ds DATASTORE]" >&2
           exit 1 ;;
    esac
done

if ${export_db} && ${import_db}
  then
    printf "Selected: joined EXPORT and IMPORT mode\n"
    if [ "$datastore" == "firestore" ]
      then
        gcloud config list
        printf "Please enter the GCP project ID to export from (return if project ID is already set to this project): "
        read -r ID_src
        if [ -n "$ID_src" ]
          then
            gcloud config set project "$ID_src"
        fi
        python3 data_migration.py --collections "${collections[@]}" --file "$file" --documents "${documents[@]}" --export_db --datastore "firestore"
        printf "Please enter the GCP project ID to import data into: "
        read -r ID_dest
        gcloud config set project "$ID_dest"
        if ${overwrite}
          then
            python3 data_migration.py --collections "${collections[@]}" --file "$file" --documents "${documents[@]}" --import_db --datastore "firestore" --overwrite
        else
            python3 data_migration.py --collections "${collections[@]}" --file "$file" --documents "${documents[@]}" --import_db --datastore "firestore"
        fi
    elif [ "$datastore" == "redis" ]
      then
        printf "Export:\n"
        python3 data_migration.py --collections "${collections[@]}" --file "$file" --documents "${documents[@]}" --export_db --datastore "redis"
        printf "Import:\n"
        if ${overwrite}
          then
            python3 data_migration.py --collections "${collections[@]}" --file "$file" --documents "${documents[@]}" --import_db --datastore "redis" --overwrite
        else
            python3 data_migration.py --collections "${collections[@]}" --file "$file" --documents "${documents[@]}" --import_db --datastore "redis"
        fi
    fi

elif ${import_db}
  then
    printf "Selected: IMPORT mode\n"
    if [ "$datastore" == "firestore" ]
      then
        if ${overwrite}
          then
            python3 data_migration.py --collections "${collections[@]}" --file "$file" --documents "${documents[@]}" --datastore "firestore" --import_db --overwrite
        else
            python3 data_migration.py --collections "${collections[@]}" --file "$file" --documents "${documents[@]}" --datastore "firestore" --import_db
        fi
    elif [ "$datastore" == "redis" ]
      then
        if ${overwrite}
          then
            python3 data_migration.py --collections "${collections[@]}" --file "$file" --documents "${documents[@]}" --import_db --datastore "redis" --overwrite
        else
            python3 data_migration.py --collections "${collections[@]}" --file "$file" --documents "${documents[@]}" --datastore "redis" --import_db
        fi
    fi
elif ${export_db}
  then
    printf "Selected: EXPORT mode\n"
    if [ "$datastore" == "firestore" ]
      then
        python3 data_migration.py --collections "${collections[@]}" --file "$file" --documents "${documents[@]}" --export_db --datastore "firestore"
    elif [ "$datastore" == "redis" ]
      then
        python3 data_migration.py --collections "${collections[@]}" --file "$file" --documents "${documents[@]}" --export_db --datastore "redis"
    fi
fi
