#!/usr/bin/env bash

if export INFISICAL_TOKEN_FOR_REDIS=st.65467dd29e945b505e879be3.43d087e510ae867b0fb17d45ae2f7d45.701561e9ee14b87d912e80577177cc69; then
            if python manage.py makemigrations; then
                if python manage.py migrate; then
                    if ! python manage.py runserver; then
                        exit 1
                    fi
                fi

            fi

    fi
# Prod init_script;
if export INFISICAL_TOKEN_FOR_REDIS_prod=st.65467dfd4664587dc0f0b49d.fe54ee8bc3311f141e0b4a438d42962f.ac5db3fbd525f5178eae351d34f1917f; then
        if export INFISICAL_TOKEN_FOR_PG_prod=st.65467e345cd2f14fb4917667.038f31619a608b25074237cb896992de.de24a1472a13c2240c9c2b779fc70b13; then
        if export INFISICAL_TOKEN_FOR_APP=st.65467e345cd2f14fb4917667.038f31619a608b25074237cb896992de.de24a1472a13c2240c9c2b779fc70b13; then
        if export INFISICAL_TOKEN_FOR_PG=st.65467e345cd2f14fb4917667.038f31619a608b25074237cb896992de.de24a1472a13c2240c9c2b779fc70b13; then
        if python manage.py collectstatic --noinput; then
            if python manage.py makemigrations; then
                if python manage.py migrate; then
                    if ! python manage.py runserver; then
                        exit 1
                    fi
                fi

            fi

    fi
