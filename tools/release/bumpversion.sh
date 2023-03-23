#!/bin/bash

shopt -s globstar
git config --global user.email "robot@canonical.com"
git config --global user.name "Devices Certification Bot"
git checkout -b bumpversion
pushd $(git rev-parse --show-toplevel) > /dev/null
cur_version=$(bumpversion --allow-dirty --dry-run --list ${1-minor} | grep current_version= | sed -r s,"^.*=",,)
new_version=$(bumpversion --allow-dirty --dry-run --list ${1-minor} | grep new_version= | sed -r s,"^.*=",,)
for p in **/debian; do
    pushd $(echo $p | sed -r s,"/debian",,) > /dev/null
    dch -v $new_version -D UNRELEASED ''
    popd > /dev/null
done
git add --update
pushd $(git rev-parse --show-toplevel) > /dev/null
bumpversion ${1-minor} --list --commit --allow-dirty
git push -f origin bumpversion
gh pr create -H bumpversion --title "Bump version: $cur_version → $new_version" --body "Once merged, clone the checkbox repository and run:
 - \`git tag -s \"v$new_version\" -m \"Bump version: $cur_version → $new_version\"\`
 - \`git push --tags\`
"
