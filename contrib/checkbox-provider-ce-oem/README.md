# checkbox-provider-ce-oem
This is a checkbox provider for both IoT and PC devices. And it will be built as SNAP named *checkbox-ce-oem*. 
You can define specific plugs to connect to it and start using the test jobs and plans included in checkbox-provider-ce-oem.

# Getting started
checkbox-ce-oem will define a slot *provider-ce-oem* to allow checkbox interface sanp to connect to access the test jobs and plans.

## In checkbox interface snap
You have to modify two parts and rebuild your SNAP of checkbox interface snap.
### snapcraft.yaml
Add a plug into plugs section in *snapcraft.yaml* of your checkbox interface snap.
```
example:

plugs:
    provider-ce-oem:
    interface: content
    target: $SNAP/providers/checkbox-provider-ce-oem

```
### wrapper_local
Add export PATH for checkbox-ce-oem in *wrapper_local* of your checkbox interface snap.
```
example:
export PATH="$PATH:$SNAP/usr/bin:$SNAP/usr/sbin:$SNAP/sbin:/snap/bin:$SNAP/bin:/snap/checkbox-ce-oem/current/usr/bin/:/snap/checkbox-ce-oem/current/usr/sbin"
```
### After rebuild SNAP for checkbox interface snap
Install the SNAP of checkbox interface snap and checkbox-ce-oem. Connect slot and plug of *provider-ce-oem*.

`$ sudo snap connect checkbox:provider-ce-oem checkbox-ce-oem`

### Start to using test jobs and plans in checkbox-provider-ce-oem
Now, you are able to include the job, plan or utility from checkbox-provider-ce-oem.
```
example for running a job:
$ sudo checkbox{interface snap}.checkbox-cli run com.canonical.qa.ceoem::location/gps_coordinate

example for using utility:
$ sudo checkbox{interface snap}.shell
$ checkbox{interface snap}.shell> lsmtd
```
