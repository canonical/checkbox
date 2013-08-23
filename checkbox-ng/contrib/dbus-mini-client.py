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

# TODO: Create a class to remove all global var.
current_job_path = None
service = None
session_object_path = None
session_object = None
run_list = None
desired_job_list = None
whitelist = None
exports_count = 0

def main():
    global service
    global session_object_path
    global session_object
    global run_list
    global desired_job_list
    global whitelist

    whitelist = bus.get_object(
        'com.canonical.certification.PlainBox1',
        '/plainbox/whitelist/stub'
    )

    provider = bus.get_object(
        'com.canonical.certification.PlainBox1',
        '/plainbox/provider/stubbox'
    )

    #whitelist = bus.get_object(
    #    'com.canonical.certification.PlainBox1',
    #    '/plainbox/whitelist/default'
    #)

    #provider = bus.get_object(
    #    'com.canonical.certification.PlainBox1',
    #    '/plainbox/provider/checkbox'
    #)

    #A provider manages objects other than jobs.
    provider_objects = provider.GetManagedObjects(
        dbus_interface='org.freedesktop.DBus.ObjectManager')

    #Create a session and "seed" it with my job list:
    job_list = [k for k, v in provider_objects.items() if not 'whitelist' in k]
    service = bus.get_object(
        'com.canonical.certification.PlainBox1',
        '/plainbox/service1'
    )
    session_object_path = service.CreateSession(
        job_list,
        dbus_interface='com.canonical.certification.PlainBox.Service1'
    )
    session_object = bus.get_object(
        'com.canonical.certification.PlainBox1',
        session_object_path
    )

    if session_object.PreviousSessionFile():
        if ask_for_resume():
            session_object.Resume()
        else:
            session_object.Clean()

    #to get only the *jobs* that are designated by the whitelist.
    desired_job_list = [
        object for object in provider_objects if whitelist.Designates(
            object,
            dbus_interface='com.canonical.certification.PlainBox.WhiteList1')]

    desired_local_job_list = sorted([
        object for object in desired_job_list if
        bus.get_object('com.canonical.certification.PlainBox1', object).Get(
            'com.canonical.certification.CheckBox.JobDefinition1',
            'plugin') == 'local'
    ])

    #Now I update the desired job list.
    session_object.UpdateDesiredJobList(
        desired_local_job_list,
        dbus_interface='com.canonical.certification.PlainBox.Session1'
    )

    #Now, the run_list contains the list of jobs I actually need to run \o/
    run_list = session_object.Get(
        'com.canonical.certification.PlainBox.Session1',
        'run_list'
    )

    # Add some signal receivers
    bus.add_signal_receiver(
        catchall_local_job_result_available_signals_handler,
        dbus_interface="com.canonical.certification.PlainBox.Service1",
        signal_name="JobResultAvailable")

    # Start running jobs
    print("[ Running All Local Jobs ]".center(80, '='))
    run_local_jobs()

    #PersistentSave can be called at any point to checkpoint session state.
    #In here, we're just calling it at the end, as an example.
    print("[ Saving the session ]".center(80, '='))
    session_object.PersistentSave()


def ask_for_outcome(prompt=None, allowed=None):
    if prompt is None:
        prompt = "what is the outcome? "
    if allowed is None:
        allowed = (IJobResult.OUTCOME_PASS, "p",
                   IJobResult.OUTCOME_FAIL, "f",
                   IJobResult.OUTCOME_SKIP, "s")
    answer = None
    while answer not in allowed:
        print("Allowed answers are: {}".format(", ".join(allowed)))
        answer = input(prompt)
        # Useful shortcuts for testing
        if answer == "f":
            answer = IJobResult.OUTCOME_FAIL
        if answer == "p":
            answer = IJobResult.OUTCOME_PASS
        if answer == "s":
            answer = IJobResult.OUTCOME_SKIP
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

def ask_for_resume():
    prompt = "Do you want to resume the previous session [Y/n]? "
    allowed = ('', 'y', 'Y', 'n', 'N')
    answer = None
    while answer not in allowed:
        answer = input(prompt)
    return False if answer in ('n', 'N') else True


# Asynchronous calls need reply handlers
def handle_export_reply(s):
    print("Export to buffer: I got {} bytes of export data".format(len(s)))
    maybe_quit_after_export()

def handle_export_to_file_reply(s):
    print("Export to file: completed to {}".format(s))
    maybe_quit_after_export()

def maybe_quit_after_export():
    # Two asynchronous callbacks calling this may result in a race
    # condition. Don't do this at home, use a semaphore or lock.
    global exports_count
    exports_count += 1
    if exports_count >= 2:
        loop.quit()

def handle_error(e):
    print(str(e))
    loop.quit()


def catchall_ask_for_outcome_signals_handler(current_runner_path):
    global current_job_path
    job_def_object = bus.get_object(
        'com.canonical.certification.PlainBox1', current_job_path)
    job_cmd = job_def_object.Get(
        'com.canonical.certification.CheckBox.JobDefinition1',
        'command')
    job_runner_object = bus.get_object(
        'com.canonical.certification.PlainBox1', current_runner_path)
    if job_cmd:
        run_test = ask_for_test()
        if run_test == 'y':
            job_runner_object.RunCommand()
            return
    outcome = ask_for_outcome()
    comments = 'Test plainbox comments'
    job_runner_object.SetOutcome(
        outcome,
        comments,
        dbus_interface='com.canonical.certification.PlainBox.RunningJob1')


def catchall_io_log_generated_signals_handler(offset, name, data):
    try:
        print("(<{}:{:05}>) {}".format(
            name, int(offset), data.decode('UTF-8').rstrip()))
    except UnicodeDecodeError:
        pass


def catchall_local_job_result_available_signals_handler(job, result):
    # XXX: check if the job path actually matches the current_job_path
     # Update the session job state map and run new jobs
    global session_object
    session_object.UpdateJobResult(
        job, result,
        reply_handler=run_local_jobs,
        error_handler=handle_error,
        dbus_interface='com.canonical.certification.PlainBox.Session1')


def catchall_job_result_available_signals_handler(job, result):
    # XXX: check if the job path actually matches the current_job_path
     # Update the session job state map and run new jobs
    global session_object
    session_object.UpdateJobResult(
        job, result,
        reply_handler=run_jobs,
        error_handler=handle_error,
        dbus_interface='com.canonical.certification.PlainBox.Session1')


def run_jobs():
    global run_list
    #Now the actual run, job by job.
    if run_list:
        job_path = run_list.pop(0)
        global current_job_path
        global session_object_path
        current_job_path = job_path
        job_def_object = bus.get_object(
            'com.canonical.certification.PlainBox', current_job_path)
        job_name = job_def_object.Get(
            'com.canonical.certification.PlainBox.JobDefinition1', 'name')
        job_desc = job_def_object.Get(
            'com.canonical.certification.PlainBox.JobDefinition1',
            'description')
        print("[ {} ]".format(job_name).center(80, '-'))
        if job_desc:
            print(job_desc)
            print("^" * len(job_desc.splitlines()[-1]))
            print()
        service.RunJob(session_object_path, job_path)
    else:
        show_results()


def run_local_jobs():
    global run_list
    global desired_job_list
    global whitelist
    if run_list:
        job_path = run_list.pop(0)
        global current_job_path
        global session_object_path
        current_job_path = job_path
        job_def_object = bus.get_object(
            'com.canonical.certification.PlainBox1', current_job_path)
        job_name = job_def_object.Get(
            'com.canonical.certification.PlainBox.JobDefinition1', 'name')
        job_desc = job_def_object.Get(
            'com.canonical.certification.PlainBox.JobDefinition1',
            'description')
        print("[ {} ]".format(job_name).center(80, '-'))
        if job_desc:
            print(job_desc)
        service.RunJob(session_object_path, job_path)
    else:
        #Now I update the desired job list to get jobs created from local jobs.
        session_object.UpdateDesiredJobList(
            desired_job_list,
            dbus_interface='com.canonical.certification.PlainBox.Session1'
        )
        bus.add_signal_receiver(
            catchall_ask_for_outcome_signals_handler,
            dbus_interface="com.canonical.certification.PlainBox.Service1",
            signal_name="AskForOutcome")

        bus.add_signal_receiver(
            catchall_io_log_generated_signals_handler,
            dbus_interface="com.canonical.certification.PlainBox.Service1",
            signal_name="IOLogGenerated",
            byte_arrays=True)  # To easily convert the byte arrays to strings

        # Replace the job result handler we created for local jobs for by the
        # one dedicated to regular job types
        bus.remove_signal_receiver(
            catchall_local_job_result_available_signals_handler,
            dbus_interface="com.canonical.certification.PlainBox.Service1",
            signal_name="JobResultAvailable")

        bus.add_signal_receiver(
            catchall_job_result_available_signals_handler,
            dbus_interface="com.canonical.certification.PlainBox.Service1",
            signal_name="JobResultAvailable")

        job_list = session_object.Get(
            'com.canonical.certification.PlainBox.Session1',
            'job_list'
        )

        #to get only the *jobs* that are designated by the whitelist.
        desired_job_list = [
            object for object in job_list if whitelist.Designates(
                object,
                dbus_interface=
                'com.canonical.certification.PlainBox.WhiteList1')]

        #Now I update the desired job list.
        # XXX: Remove previous local jobs from this list to avoid evaluating
        # them twice
        session_object.UpdateDesiredJobList(
            desired_job_list,
            dbus_interface='com.canonical.certification.PlainBox.Session1'
        )

        #Now, the run_list contains the list of jobs I actually need to run \o/
        run_list = session_object.Get(
            'com.canonical.certification.PlainBox.Session1',
            'run_list'
        )

        print("[ Running All Jobs ]".center(80, '='))
        run_jobs()


def show_results():
    global session_object_path
    session_object = bus.get_object(
        'com.canonical.certification.PlainBox1',
        session_object_path
    )
    job_state_map = session_object.Get(
        'com.canonical.certification.PlainBox.Session1', 'job_state_map')
    print("[ Results ]".center(80, '='))
    for k, job_state_path in job_state_map.items():
        job_state_object = bus.get_object(
            'com.canonical.certification.PlainBox1',
            job_state_path
        )
        # Get the job definition object and some properties
        job_def_path = job_state_object.Get(
            'com.canonical.certification.PlainBox.JobState1', 'job')
        job_def_object = bus.get_object(
            'com.canonical.certification.PlainBox1', job_def_path)
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
            'com.canonical.certification.PlainBox1', job_result_path)
        outcome = job_result_object.Get(
            'com.canonical.certification.PlainBox.Result1', 'outcome')
        comments = job_result_object.Get(
            'com.canonical.certification.PlainBox.Result1', 'comments')
        io_log = job_result_object.Get(
            'com.canonical.certification.PlainBox.Result1',
            'io_log', byte_arrays=True)

        print("{:55s} {:15s} {}".format(job_name, outcome, comments))
    export_session()

def export_session():
    service.ExportSessionToFile(
        session_object_path,
        "xml",
        [''],
        "/tmp/report.xml",
        reply_handler=handle_export_to_file_reply,
        error_handler=handle_error
    )
    # The exports will apparently run in parallel. The callbacks
    # are responsible for ensuring exiting after this.
    service.ExportSession(
        session_object_path,
        "xml",
        [''],
        reply_handler=handle_export_reply,
        error_handler=handle_error
    )

# Start the first call after a short delay
GObject.timeout_add(5, main)
loop = GObject.MainLoop()
loop.run()

# Stop the Plainbox dbus service
service.Exit()
