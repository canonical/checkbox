# checkbox-provider-arm
This is a checkbox provider for all ARM architecture platforms. And it will be built as SNAP named *checkbox-arm*. 
You can define specific plugs to connect to it and start using the test jobs and plans included in checkbox-provider-arm.

# Getting started
checkbox-arm will define a slot *provider-arm* to allow checkbox-project to connect to access the test jobs and plans.

## In checkbox-project
You have to modify two parts and rebuild your SNAP of checkbox-project.
### snapcraft.yaml
Add a plug into plugs section in *snapcraft.yaml* of your checkbox-project.
```
example:

plugs:
    provider-arm:
    interface: content
    target: $SNAP/providers/checkbox-provider-arm
    default-provider: checkbox-arm
```
### wrapper_local
Add export PATH for checkbox-arm in *wrapper_local* of your checkbox-project.
```
example:
export PATH="$PATH:$SNAP/usr/bin:$SNAP/usr/sbin:$SNAP/sbin:/snap/bin:$SNAP/bin:/snap/checkbox-arm/current/usr/bin/:/snap/checkbox-arm/current/usr/sbin"
```
### After rebuild SNAP for checkbox-project
Install the SNAP of checkbox-project and checkbox-arm. Connect slot and plug of *provider-arm*.

`$ sudo snap connect checkbox-project:provider-arm checkbox-arm`

### Start to using test jobs and plans in checkbox-provider-arm
Now, you are able to include the job, plan or utility from checkbox-provider-arm.
```
example for running a job:
$ sudo checkbox-project.checkbox-cli run com.canonical.qa.arm::location/gps_coordinate

example for using utility:
$ sudo checkbox-project.shell
$ checkbox.shell> lsmtd
```
