# Building checkbox-core-snap
This snap is the core reusable part of checkbox, it includes all the utilities
and some core providers.

## Environment Creation
This small guide mainly covers offline builds with `--destructive-mode`
enabled. These builds must be carried out in single-use containers as the name
implies. This guide will explain how to build the `series22` snap, in order to
build the others the process is the same, the guide will point out what to
change.

### Container configuration
Let's begin by creating the container and installing the needed packages.
```bash
# First, create the container
# Note: Always use the version of ubuntu for the snap you 
#       are building, series22 -> ubuntu22.04 (jammy)
(host) > lxd launch ubuntu:22.04 jammy
(host) > lxd exec jammy bash
# Once in the container install snapcraft.
# Note: For series16 you will need snapcraft4.x, to install
#       it use run: 
#       snap install snapcraft --classic --channel=4.x
(jammy)> snap install snapcraft --classic
# Now clone the checkbox repository
(jammy)> git clone https://github.com/canonical/checkbox
```
If you are debugging a build, this is a good step to make a backup of the
environment, so that you don't need to repeat the above steps if something
goes wrong.
```bash
(jammy)> exit
(host) > lxd snapshot jammy backup
```
If at any point you need to rollback to this backup run
```bash
(host) > lxd restore jammy backup
(host) > lxd exec jammy bash
# This you may want to do if you made any updates to the repo
# in the meantime
(jammy)> (cd checkbox && git pull)
```
### Running the build
Now let's launch the actual build
```bash
(jammy)> cd checkbox/checkbox-core-snap
# For another series, change the parameter accordingly
(jammy)> ./prepare.sh series22
(jammy)> snapcraft --destructive-mode
```
The previous will either create a `checkbox22_(version)_(arch).snap` file or
yield an error. 

If the build fails, refer to the **Recovering from a failure** chapter for some
tips!

### Testing the build
To test the build one must install it and see if the content is correct. This
process is not perfect, but one way to do it is the following:
```bash
(jammy)> snap install checkbox22_(version)_(arch).snap --dangerous
```
Now we have installed the core snap, but we can not use it directly. To use it
we need a simple user snap. 
```bash
# Note: install the correct channel for your series
(jammy)> snap install checkbox --classic --channel=22.04
```
Now you can test the checkbox snap, you can try to run test plans as follows.
For example, you may want to run the smoke test plan.
```
(jammy)> checkbox.checkbox_cli
```

### Recovering from a failure

Recovering from a failure is tricky, this is why this guide makes you create a
snapshot. Most of the time you will not need it, but sometimes it will be
necessary. Depending on what failed you may want to follow these strategies
re-run the build:

**Just re-run it:** Snapcraft will try to use cached steps for what you have
done and re-do things that you have changed in the recipe. 

**Clean parts (partial):** You can try to remove a `part` cache. To do so run
`rm -rf parts/(part_name)`. This will many problems like the part being dirty
and snapcraft being unable to overwrite what is there.

**Clean parts (all)**: Sometimes a parts dir in unrecoverably dirty and you
may be unable to clean specifically what is broken, a symptom of this is
snapcraft skipping a part thinking that it is up-to-date when it was actually
changed. To do this `rm -rf parts`.

**Clean all:** Sometimes cleaning `parts` is not enough, you can run
`git clean -xfd`, resetting the repo to a clean state. If you do this remember
you need to run `prepare.sh` again.

**Reset to the snapshot:** This is also necessary sometimes, you can find the
command above! 
