# Building checkbox-core-snap
This snap is the core reusable part of checkbox, it includes all the utilities
and some core providers. The snap can be built for multiple 
[base snaps](https://snapcraft.io/docs/base-snaps). Each recipe is in a `seriesXX`
 directory where `XX` is the base snap. For instance `series22` contains
 the `core22 or jammy` snap.

## Building guide
This section covers how to build the snap via either the `multipass` or the 
`lxd` backend. This guide will focus on the latter
but with small adjustments can be used for the former. Also, this guide will
build the `series22` snap, adjust the commands to build any other.

In order to build the snap you are going to need the following:
1. **snapcraft:** Installed via `snap install snapcraft --classic` or 
`snap install snapcraft --classic --channel=4.x` for series16
2. **python3:** Installed via `apt` or any other packaging solution
3. **setuptools_scm:** Installed via pip
4. **rsync:** Installed via apt or any other packaging solution

After installing all the dependencies do the following:
```
> git clone https://github.com/canonical/checkbox
> cd checkbox/checkbox-core-snap/
> ./prepare.sh series22
> cd series22
```

> Note: `prepare.sh` will prepare the series creating the build environment, 
> refer to its output for further detail

Finally build the snap with:
```
> snapcraft --use-lxd
```

If the build has failed, check either the **Building guide for debugging**, if
it completed succesfully, refer to **Testing the build**.

## Testing the build
To test the build one must install it and see if the content is correct.
One way to do it is the following:

```bash
> snap install checkbox22_(version)_(arch).snap --dangerous
```
Now we have installed the core snap, but we cannnot use it directly. To use it
we need a frontend snap. 
```bash
# Note: install the correct channel for your series
> snap install checkbox --classic --channel=22.04
```
To test the checkbox snap, you can try to run test plans as follows.
For example, you may want to run the smoke test plan.
```
> checkbox.checkbox_cli
```

## Building for debugging
To build the checkbox core snap for debugging you might find 
`snapcraft --destructive-mode` executed in a single-use container a handy trick 
(see [Faster snap development – additional tips and tricks](https://snapcraft.io/blog/faster-snap-development-additional-tips-and-tricks)
for more info). 
Below you will find build steps for the series22 snap as an example 
(changes needed for earlier series pointed out where applicable).

The destructive mode is useful for debugging a build because of incremental 
build time: with direct host system one can quickly iterate on the environment
installing packages, changing versions or editing the recipe, without restarting
every build from scratch afterwards.

### Container configuration
Let's begin by creating the container and installing the needed packages.
```bash
# First, create the container
# Note: Always use the version of ubuntu for the snap you 
#       are building, series22 -> ubuntu22.04 (jammy)
(host) > lxc launch ubuntu:22.04 jammy
# Launch a shell from the container
(host) > lxc shell jammy
# Make sure the package repositories are up-to-date and install
# the required packages
(jammy)> apt update
(jammy)> apt install python3-setuptools-scm git snapd
# Install snapcraft.
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
(host) > lxc snapshot jammy backup
```
If at any point you need to rollback to this backup run
```bash
(host) > lxc restore jammy backup
(host) > lxc shell jammy
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

If the build completes, refer to the **Testing the build**, remember to follow
that guide from within the container you have created in this chapter!

### Recovering from a failure

Recovering from a failure is tricky, which is why you should create a
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


