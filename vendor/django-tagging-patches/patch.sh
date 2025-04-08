#!/usr/bin/env bash
cat \
Use-smart_str-instead-of-deprecated-smart_text-Django-fun.patch \
Use-re_path-instead-of-deprecated-url-Django-function.patch \
Add-support-for-Django-4-compatibility.patch \
Check-FullResultSet-exception.patch \
python3.11.patch \
python3.12.patch \
| patch -t -p1 -d ../django-tagging