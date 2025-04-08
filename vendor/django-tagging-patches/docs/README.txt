
Background:
django-tagging is no longer maintained and latest version is 0.5.0
django 4.2 breaks django-tagging in a few places

Source from:
https://django-tagging.readthedocs.io/en/develop/#installing-an-official-release
git clone git@github.com:Fantomas42/django-tagging.git

Patches from:
https://sources.debian.org/patches/python-django-tagging/1:0.5.0-5.1/

Patching:
./patch.sh applies the patches in the correct order to ../django-tagging

