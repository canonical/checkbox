#!/usr/bin/env python3
########
#This simple script provides a small reference and example of how to
#invoke plainbox methods through d-bus to accomplish useful tasks.
#
#Use of the d-feet tool is suggested for interactive exploration of
#the plainbox objects, interfaces and d-bus API. However, d-feet can be
#cumbersome to use for more advanced testing and experimentation.
#
#This script can be adapted to fit other testing needs as well.
#
#To run it, first launch plainbox in service mode using the stub provider:
#    $ plainbox -c stub service
#
#then run the script itself. It does the following things:
#
# 1- Obtain a whitelist and a job provider
# 2- Use the whitelist to "qualify" jobs offered by the provider,
#    In essence filtering them to obtain a desired list of jobs to run.
# 3- Run each job in the run_list, this implicitly updates the session's
#    results and state map.
# 4- Print the job names and outcomes and some other data
# 5- Export the session's data (job results) to json in /tmp.
#####

import dbus

bus = dbus.SessionBus()

whitelist = bus.get_object(
    'com.canonical.certification.PlainBox',
    '/plainbox/whitelist/stub'
)

provider = bus.get_object(
    'com.canonical.certification.PlainBox',
    '/plainbox/provider/stubbox'
)

#A provider manages objects other than jobs.
provider_objects = provider.GetManagedObjects(dbus_interface='org.freedesktop.DBus.ObjectManager')

#Create a session and "seed" it with my job list:

job_list = [k for k, v in provider_objects.items() if not 'whitelist' in k]

service = bus.get_object(
    'com.canonical.certification.PlainBox',
    '/plainbox/service1'
)
session_object_path = service.CreateSession(
    job_list,
    dbus_interface='com.canonical.certification.PlainBox.Service1'
)
session_object = bus.get_object(
    'com.canonical.certification.PlainBox',
    session_object_path
)

#to get only the *jobs* that are designated by the whitelist.
desired_job_list = [object for object in provider_objects if whitelist.Designates(object, dbus_interface='com.canonical.certification.PlainBox.WhiteList1')]

#Now I update the desired job list.
session_object.UpdateDesiredJobList(
    desired_job_list,
    dbus_interface='com.canonical.certification.PlainBox.Session1'
)

#Now, the run_list contains the list of jobs I actually need to run \o/
run_list = session_object.Get(
    'com.canonical.certification.PlainBox.Session1',
    'run_list'
)

#Now the actual run, job by job.
for job_path in run_list:
    service.RunJob(session_object_path, job_path)
    #After running each job, re-update the desired job list.
    #This is needed so that we scan for newly created jobs in the
    #native session object, and ensure their JobDefinition and JobState
    #wrappers are created and published.
    session_object.UpdateDesiredJobList(
        desired_job_list,
        dbus_interface='com.canonical.certification.PlainBox.Session1'
    )

job_state_map = session_object.Get('com.canonical.certification.PlainBox.Session1', 'job_state_map')

for k, job_state_path in job_state_map.items():
    job_state_object = bus.get_object(
        'com.canonical.certification.PlainBox',
        job_state_path
    )
    # Get the job definition object and some properties
    job_def_path = job_state_object.Get('com.canonical.certification.PlainBox.JobState1', 'job')
    job_def_object = bus.get_object('com.canonical.certification.PlainBox', job_def_path)
    job_name = job_def_object.Get('com.canonical.certification.PlainBox.JobDefinition1', 'name')
    # Ask the via value (e.g. to comptute job categories) if a job is a child of a local job
    job_via = job_def_object.Get('com.canonical.certification.CheckBox.JobDefinition1', 'via')

    # Get the current job result object and the outcome property
    job_result_path = job_state_object.Get('com.canonical.certification.PlainBox.JobState1', 'result')
    job_result_object = bus.get_object('com.canonical.certification.PlainBox', job_result_path)
    outcome = job_result_object.Get('com.canonical.certification.PlainBox.Result1', 'outcome')

    print(job_name, "via {}".format(job_via) if job_via else '', outcome)

#Now let's export the session's result.

output_file = service.ExportSession(session_object_path,
                                    "json",
                                    ['with-io-log', 'with-job-via'],
                                    "/tmp/report.json",
                                    dbus_interface='com.canonical.certification.PlainBox.Service1')
