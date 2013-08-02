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
# 5- Export the session's data (job results) to xml in /tmp.
#####

import dbus
from gi.repository import GObject
from dbus.mainloop.glib import DBusGMainLoop
from plainbox.abc import IJobResult

bus = dbus.SessionBus(mainloop=DBusGMainLoop())

whitelist = bus.get_object(
    'com.canonical.certification.PlainBox',
    '/plainbox/whitelist/stub'
)

provider = bus.get_object(
    'com.canonical.certification.PlainBox',
    '/plainbox/provider/stubbox'
)

#A provider manages objects other than jobs.
provider_objects = provider.GetManagedObjects(
    dbus_interface='org.freedesktop.DBus.ObjectManager')

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
desired_job_list = [
    object for object in provider_objects if whitelist.Designates(
        object,
        dbus_interface='com.canonical.certification.PlainBox.WhiteList1')]

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

current_job_path = None


def ask_for_outcome(prompt=None, allowed=None):
    if prompt is None:
        prompt = "what is the outcome? "
    if allowed is None:
        allowed = (IJobResult.OUTCOME_PASS,
                   IJobResult.OUTCOME_FAIL,
                   IJobResult.OUTCOME_SKIP)
    answer = None
    while answer not in allowed:
        print("Allowed answers are: {}".format(", ".join(allowed)))
        answer = input(prompt)
    return answer


def ask_for_test(prompt=None, allowed=None):
    if prompt is None:
        prompt = "Run the test command? "
    if allowed is None:
        allowed = ("y",
                   "n",
                   )
    answer = None
    while answer not in allowed:
        print("Allowed answers are: {}".format(", ".join(allowed)))
        answer = input(prompt)
    return answer


# Asynchronous calls need reply handlers
def handle_export_reply(s):
    print("Export completed to {}".format(s))
    loop.quit()


def handle_error(e):
    print(str(e))
    loop.quit()


def catchall_ask_for_outcome_signals_handler(current_runner_path):
    global current_job_path
    job_def_object = bus.get_object(
        'com.canonical.certification.PlainBox', current_job_path)
    job_desc = job_def_object.Get(
        'com.canonical.certification.PlainBox.JobDefinition1',
        'description')
    job_cmd = job_def_object.Get(
        'com.canonical.certification.CheckBox.JobDefinition1',
        'command')
    job_runner_object = bus.get_object(
        'com.canonical.certification.PlainBox', current_runner_path)
    print(job_desc)
    if job_cmd:
        run_test = ask_for_test()
        if run_test == 'y':
            job_runner_object.RunCommand()
            return
    outcome = ask_for_outcome()
    job_runner_object.SetOutcome(
        outcome,
        dbus_interface='com.canonical.certification.PlainBox.RunningJob1')


def catchall_io_log_generated_signals_handler(offset, name, data):
    try:
        print("(<{}:{:05}>) {}".format(
            name, int(offset), data.decode('UTF-8').rstrip()))
    except UnicodeDecodeError:
        pass


def properties_changed(interface, changed_properties, invalidated_properties):
    for p in changed_properties:
        print("{} PropertiesChanged: {}".format(interface, p))
    if interface == 'com.canonical.certification.PlainBox.Session1':
        if 'job_state_map' in changed_properties:
            #After running each job, re-update the desired job list.
            #This is needed so that we scan for newly created jobs in the
            #native session object, and ensure their JobDefinition and JobState
            #wrappers are created and published.
            session_object.UpdateDesiredJobList(
                desired_job_list,
                dbus_interface='com.canonical.certification.PlainBox.Session1'
            )
            # Run next job
            run_jobs()


def run_jobs():
    #Now the actual run, job by job.
    if run_list:
        job_path = run_list.pop(0)
        global current_job_path
        current_job_path = job_path
        service.RunJob(session_object_path, job_path)
    else:
        show_results()


def show_results():
    job_state_map = session_object.Get(
        'com.canonical.certification.PlainBox.Session1', 'job_state_map')
    for k, job_state_path in job_state_map.items():
        job_state_object = bus.get_object(
            'com.canonical.certification.PlainBox',
            job_state_path
        )
        # Get the job definition object and some properties
        job_def_path = job_state_object.Get(
            'com.canonical.certification.PlainBox.JobState1', 'job')
        job_def_object = bus.get_object(
            'com.canonical.certification.PlainBox', job_def_path)
        job_name = job_def_object.Get(
            'com.canonical.certification.PlainBox.JobDefinition1', 'name')
        # Ask the via value (e.g. to comptute job categories)
        # if a job is a child of a local job
        job_via = job_def_object.Get(
            'com.canonical.certification.CheckBox.JobDefinition1', 'via')

        # Get the current job result object and the outcome property
        job_result_path = job_state_object.Get(
            'com.canonical.certification.PlainBox.JobState1', 'result')
        job_result_object = bus.get_object(
            'com.canonical.certification.PlainBox', job_result_path)
        outcome = job_result_object.Get(
            'com.canonical.certification.PlainBox.Result1', 'outcome')
        comments = job_result_object.Get(
            'com.canonical.certification.PlainBox.Result1', 'comments')
        io_log = job_result_object.Get(
            'com.canonical.certification.PlainBox.Result1',
            'io_log', byte_arrays=True)

        print(job_name, "via {}".format(job_via) if job_via else '',
              outcome, comments, io_log)
    export_session()


def export_session():
    service.ExportSession(
        session_object_path,
        "xml",
        [''],
        "/tmp/report.xml",
        reply_handler=handle_export_reply,
        error_handler=handle_error
    )

# Add some signal receivers
bus.add_signal_receiver(
    catchall_ask_for_outcome_signals_handler,
    dbus_interface="com.canonical.certification.PlainBox.Service1",
    signal_name="AskForOutcome")

bus.add_signal_receiver(
    catchall_io_log_generated_signals_handler,
    dbus_interface="com.canonical.certification.PlainBox.Service1",
    signal_name="IOLogGenerated",
    byte_arrays=True)  # To easily convert the byte arrays to strings

bus.add_signal_receiver(
    properties_changed,
    dbus_interface=dbus.PROPERTIES_IFACE,
    signal_name="PropertiesChanged")

# Start the first call after a short delay
GObject.timeout_add(5, run_jobs)
loop = GObject.MainLoop()
loop.run()

# Stop the Plainbox dbus service
service.Exit()
