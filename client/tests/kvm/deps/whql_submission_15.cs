// DTM submission automation program
// Author: Michael Goldish <mgoldish@redhat.com>
// Based on sample code by Microsoft.

// Note: this program has only been tested with DTM version 1.5.
// It might fail to work with other versions, specifically because it uses
// a few undocumented methods/attributes.

using System;
using System.Collections.Generic;
using System.Text.RegularExpressions;
using Microsoft.DistributedAutomation.DeviceSelection;
using Microsoft.DistributedAutomation.SqlDataStore;

namespace automate0
{
    class AutoJob
    {
        static int Main(string[] args)
        {
            if (args.Length != 5)
            {
                Console.WriteLine("Error: incorrect number of command line arguments");
                Console.WriteLine("Usage: {0} serverName clientName machinePoolName submissionName timeout",
                    System.Environment.GetCommandLineArgs()[0]);
                return 1;
            }
            string serverName = args[0];
            string clientName = args[1];
            string machinePoolName = args[2];
            string submissionName = args[3];
            double timeout = Convert.ToDouble(args[4]);

            try
            {
                // Initialize DeviceScript and connect to data store
                Console.WriteLine("Initializing DeviceScript object");
                DeviceScript script = new DeviceScript();
                Console.WriteLine("Connecting to data store");

                script.ConnectToNamedDataStore(serverName);

                // Find client machine
                IResourcePool rootPool = script.GetResourcePoolByName("$");
                Console.WriteLine("Looking for client machine '{0}'", clientName);
                IResource machine = null;
                while (true)
                {
                    try
                    {
                        machine = rootPool.GetResourceByName(clientName);
                    }
                    catch (Exception e)
                    {
                        Console.WriteLine("Warning: " + e.Message);
                    }
                    // Make sure the machine is valid
                    if (machine != null &&
                        machine.OperatingSystem != null &&
                        machine.OperatingSystem.Length > 0 &&
                        machine.ProcessorArchitecture != null &&
                        machine.ProcessorArchitecture.Length > 0 &&
                        machine.GetDevices().Length > 0)
                        break;
                    System.Threading.Thread.Sleep(1000);
                }
                Console.WriteLine("Client machine '{0}' found ({1}, {2})",
                    clientName, machine.OperatingSystem, machine.ProcessorArchitecture);

                // Create machine pool and add client machine to it
                // (this must be done because jobs cannot be scheduled for machines in the
                // default pool)
                try
                {
                    script.CreateResourcePool(machinePoolName, rootPool.ResourcePoolId);
                }
                catch (Exception e)
                {
                    Console.WriteLine("Warning: " + e.Message);
                }
                IResourcePool newPool = script.GetResourcePoolByName(machinePoolName);
                Console.WriteLine("Moving the client machine to pool '{0}'", machinePoolName);
                machine.ChangeResourcePool(newPool);

                // Reset client machine
                if (machine.Status != "Ready")
                {
                    Console.WriteLine("Changing the client machine's status to 'Reset'");
                    while (true)
                    {
                        try
                        {
                            machine = rootPool.GetResourceByName(clientName);
                            machine.ChangeResourceStatus("Unsafe");
                            System.Threading.Thread.Sleep(5000);
                            machine.ChangeResourceStatus("Reset");
                            break;
                        }
                        catch (Exception e)
                        {
                            Console.WriteLine("Warning: " + e.Message);
                        }
                        System.Threading.Thread.Sleep(5000);
                    }
                    Console.WriteLine("Waiting for client machine to be ready");
                    while (machine.Status != "Ready")
                    {
                        try
                        {
                            machine = rootPool.GetResourceByName(clientName);
                        }
                        catch (Exception e)
                        {
                            Console.WriteLine("Warning: " + e.Message);
                        }
                        System.Threading.Thread.Sleep(1000);
                    }
                }
                Console.WriteLine("Client machine is ready");

                // Get requested device regex and look for a matching device
                Console.WriteLine("Device to test: ");
                Regex deviceRegex = new Regex(Console.ReadLine(), RegexOptions.IgnoreCase);
                Console.WriteLine("Looking for device '{0}'", deviceRegex);
                IDevice device;
                DateTime endTime = DateTime.Now.AddSeconds(120);
                while (DateTime.Now < endTime)
                {
                    machine = rootPool.GetResourceByName(clientName);
                    Console.WriteLine("(Client machine has {0} devices)", machine.GetDevices().Length);
                    foreach (IDevice d in machine.GetDevices())
                    {
                        if (deviceRegex.IsMatch(d.FriendlyName))
                        {
                            device = d;
                            goto deviceFound;
                        }
                    }
                    System.Threading.Thread.Sleep(5000);
                }
                Console.WriteLine("Error: device '{0}' not found", deviceRegex);
                return 1;

            deviceFound:
                Console.WriteLine("Found device '{0}'", device.FriendlyName);

                // Get requested jobs regex
                Console.WriteLine("Jobs to run: ");
                Regex jobRegex = new Regex(Console.ReadLine(), RegexOptions.IgnoreCase);

                // Create submission
                Object[] existingSubmissions = script.GetSubmissionByName(submissionName);
                if (existingSubmissions.Length > 0)
                {
                    Console.WriteLine("Submission '{0}' already exists -- removing it",
                        submissionName);
                    script.DeleteSubmission(((ISubmission)existingSubmissions[0]).Id);
                }
                Console.WriteLine("Creating submission '{0}'", submissionName);
                ISubmission submission = script.CreateHardwareSubmission(submissionName,
                    newPool.ResourcePoolId, device.InstanceId);

                // Get DeviceData objects from the user
                List<Object> deviceDataList = new List<Object>();
                while (true)
                {
                    ISubmissionDeviceData dd = script.CreateNewSubmissionDeviceData();
                    Console.WriteLine("DeviceData name: ");
                    dd.Name = Console.ReadLine();
                    if (dd.Name.Length == 0)
                        break;
                    Console.WriteLine("DeviceData data: ");
                    dd.Data = Console.ReadLine();
                    deviceDataList.Add(dd);
                }

                // Set the submission's DeviceData
                submission.SetDeviceData(deviceDataList.ToArray());

                // Get descriptors from the user
                List<Object> descriptorList = new List<Object>();
                while (true)
                {
                    Console.WriteLine("Descriptor path: ");
                    string descriptorPath = Console.ReadLine();
                    if (descriptorPath.Length == 0)
                        break;
                    descriptorList.Add(script.GetDescriptorByPath(descriptorPath));
                }

                // Set the submission's descriptors
                submission.SetLogoDescriptors(descriptorList.ToArray());

                // Create a schedule
                ISchedule schedule = script.CreateNewSchedule();
                Console.WriteLine("Scheduling jobs:");
                int jobCount = 0;
                foreach (IJob j in submission.GetJobs())
                {
                    if (jobRegex.IsMatch(j.Name))
                     {
                        Console.WriteLine("  " + j.Name);
                        schedule.AddDeviceJob(device, j);
                        jobCount++;
                    }
                }
                if (jobCount == 0)
                {
                    Console.WriteLine("Error: no submission jobs match pattern '{0}'", jobRegex);
                    return 1;
                }
                schedule.AddSubmission(submission);
                schedule.SetResourcePool(newPool);
                script.RunSchedule(schedule);

                // Wait for jobs to complete
                Console.WriteLine("Waiting for all jobs to complete (timeout={0})", timeout);
                endTime = DateTime.Now.AddSeconds(timeout);
                int numCompleted = 0, numFailed = 0;
                while (numCompleted < submission.GetResults().Length && DateTime.Now < endTime)
                {
                    // Sleep for 30 seconds
                    System.Threading.Thread.Sleep(30000);
                    // Count completed submission jobs
                    numCompleted = 0;
                    foreach (IResult r in submission.GetResults())
                        if (r.ResultStatus != "InProgress")
                            numCompleted++;
                    // Report results in a Python readable format and count failed schedule jobs
                    // (submission jobs are a subset of schedule jobs)
                    Console.WriteLine();
                    Console.WriteLine("---- [");
                    numFailed = 0;
                    foreach (IResult r in schedule.GetResults())
                    {
                        Console.WriteLine("  {");
                        Console.WriteLine("    'id': {0}, 'job': r'''{1}''',", r.Job.Id, r.Job.Name);
                        Console.WriteLine("    'logs': r'''{0}''',", r.LogLocation);
                        if (r.ResultStatus != "InProgress")
                            Console.WriteLine("    'report': r'''{0}''',",
                                submission.GetSubmissionResultReport(r));
                        Console.WriteLine("    'status': '{0}',", r.ResultStatus);
                        Console.WriteLine("    'pass': {0}, 'fail': {1}, 'notrun': {2}, 'notapplicable': {3}",
                            r.Pass, r.Fail, r.NotRun, r.NotApplicable);
                        Console.WriteLine("  },");
                        numFailed += r.Fail;
                    }
                    Console.WriteLine("] ----");
                }
                Console.WriteLine();

                // Cancel incomplete jobs
                foreach (IResult r in schedule.GetResults())
                    if (r.ResultStatus == "InProgress")
                        r.Cancel();

                // Set the machine's status to Unsafe and then Reset
                try
                {
                    machine = rootPool.GetResourceByName(clientName);
                    machine.ChangeResourceStatus("Unsafe");
                    System.Threading.Thread.Sleep(5000);
                    machine.ChangeResourceStatus("Reset");
                }
                catch (Exception e)
                {
                    Console.WriteLine("Warning: " + e.Message);
                }

                // Report failures
                if (numCompleted < submission.GetResults().Length)
                    Console.WriteLine("Some jobs did not complete on time.");
                if (numFailed > 0)
                    Console.WriteLine("Some jobs failed.");

                if (numFailed > 0 || numCompleted < submission.GetResults().Length)
                    return 1;

                Console.WriteLine("All jobs completed.");
                return 0;
            }
            catch (Exception e)
            {
                Console.WriteLine("Error: " + e.Message);
                return 1;
            }
        }
    }
}
