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
        // Wait for a machine to show up in the data store
        static void FindMachine(IResourcePool rootPool, string machineName)
        {
            Console.WriteLine("Looking for machine '{0}'", machineName);
            IResource machine = null;
            while (true)
            {
                try
                {
                    machine = rootPool.GetResourceByName(machineName);
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
                machineName, machine.OperatingSystem, machine.ProcessorArchitecture);
        }

        // Delete a machine pool if it exists
        static void DeleteResourcePool(IDeviceScript script, string poolName)
        {
            while (true)
            {
                try
                {
                    IResourcePool pool = script.GetResourcePoolByName(poolName);
                    if (pool != null)
                        script.DeleteResourcePool(pool);
                    break;
                }
                catch (Exception e)
                {
                    Console.WriteLine("Warning: " + e.Message);
                    System.Threading.Thread.Sleep(1000);
                }
            }
        }

        // Set the machine's status to 'Reset' and optionally wait for it to become ready
        static void ResetMachine(IResourcePool rootPool, string machineName, bool wait)
        {
            Console.WriteLine("Resetting machine '{0}'", machineName);
            IResource machine;
            while (true)
            {
                try
                {
                    machine = rootPool.GetResourceByName(machineName);
                    machine.ChangeResourceStatus("Reset");
                    break;
                }
                catch (Exception e)
                {
                    Console.WriteLine("Warning: " + e.Message);
                    System.Threading.Thread.Sleep(5000);
                }
            }
            if (wait)
            {
                Console.WriteLine("Waiting for machine '{0}' to be ready", machineName);
                while (machine.Status != "Ready")
                {
                    try
                    {
                        machine = rootPool.GetResourceByName(machineName);
                    }
                    catch (Exception e)
                    {
                        Console.WriteLine("Warning: " + e.Message);
                    }
                    System.Threading.Thread.Sleep(1000);
                }
                Console.WriteLine("Machine '{0}' is ready", machineName);
            }
        }

        // Look for a device in a machine, and if not found, keep trying for 3 minutes
        static IDevice GetDevice(IResourcePool rootPool, string machineName, string regexStr)
        {
            Regex deviceRegex = new Regex(regexStr, RegexOptions.IgnoreCase);
            int numAttempts = 1;
            DateTime endTime = DateTime.Now.AddSeconds(180);
            while (DateTime.Now < endTime)
            {
                IResource machine = rootPool.GetResourceByName(machineName);
                Console.WriteLine("Looking for device '{0}' in machine '{1}' (machine has {2} devices)",
                    regexStr, machineName, machine.GetDevices().Length);
                foreach (IDevice d in machine.GetDevices())
                {
                    if (deviceRegex.IsMatch(d.FriendlyName))
                    {
                        Console.WriteLine("Found device '{0}'", d.FriendlyName);
                        return d;
                    }
                }
                Console.WriteLine("Device not found");
                if (numAttempts % 5 == 0)
                    ResetMachine(rootPool, machineName, true);
                else
                    System.Threading.Thread.Sleep(5000);
                numAttempts++;
            }
            Console.WriteLine("Error: device '{0}' not found", deviceRegex);
            return null;
        }

        static int Main(string[] args)
        {
            if (args.Length < 5)
            {
                Console.WriteLine("Error: incorrect number of command line arguments");
                Console.WriteLine("Usage: {0} serverName machinePoolName submissionName timeout machineName0 machineName1 ...",
                    System.Environment.GetCommandLineArgs()[0]);
                return 1;
            }
            string serverName = args[0];
            string machinePoolName = args[1];
            string submissionName = args[2];
            double timeout = Convert.ToDouble(args[3]);

            List<string> machines = new List<string>();
            for (int i = 4; i < args.Length; i++)
                machines.Add(args[i]);

            try
            {
                // Initialize DeviceScript and connect to data store
                Console.WriteLine("Initializing DeviceScript object");
                DeviceScript script = new DeviceScript();
                Console.WriteLine("Connecting to data store");
                script.ConnectToNamedDataStore(serverName);

                // Wait for client machines to become available
                IResourcePool rootPool = script.GetResourcePoolByName("$");
                foreach (string machineName in machines)
                    FindMachine(rootPool, machineName);

                // Delete the machine pool if it already exists
                DeleteResourcePool(script, machinePoolName);

                // Create the machine pool and add the client machines to it
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
                foreach (string machineName in machines)
                {
                    Console.WriteLine("Moving machine '{0}' to pool '{1}'", machineName, machinePoolName);
                    rootPool.GetResourceByName(machineName).ChangeResourcePool(newPool);
                }

                // Reset client machine
                foreach (string machineName in machines)
                    ResetMachine(rootPool, machineName, true);

                // Get requested device regex and look for a matching device in the first machine
                Console.WriteLine("Device to test:");
                IDevice device = GetDevice(rootPool, machines[0], Console.ReadLine());
                if (device == null)
                    return 1;

                // Get requested jobs regex
                Console.WriteLine("Jobs to run:");
                Regex jobRegex = new Regex(Console.ReadLine(), RegexOptions.IgnoreCase);

                // Create a submission
                Object[] existingSubmissions = script.GetSubmissionByName(submissionName);
                if (existingSubmissions.Length > 0)
                {
                    Console.WriteLine("Submission '{0}' already exists -- removing it",
                        submissionName);
                    script.DeleteSubmission(((ISubmission)existingSubmissions[0]).Id);
                }
                string hardwareId = device.InstanceId.Remove(device.InstanceId.LastIndexOf("\\"));
                Console.WriteLine("Creating submission '{0}' (hardware ID: {1})", submissionName, hardwareId);
                ISubmission submission = script.CreateHardwareSubmission(submissionName, newPool.ResourcePoolId, hardwareId);

                // Set submission DeviceData
                List<Object> deviceDataList = new List<Object>();
                while (true)
                {
                    ISubmissionDeviceData dd = script.CreateNewSubmissionDeviceData();
                    Console.WriteLine("DeviceData name:");
                    dd.Name = Console.ReadLine();
                    if (dd.Name.Length == 0)
                        break;
                    Console.WriteLine("DeviceData data:");
                    dd.Data = Console.ReadLine();
                    deviceDataList.Add(dd);
                }
                submission.SetDeviceData(deviceDataList.ToArray());

                // Set submission descriptors
                List<Object> descriptorList = new List<Object>();
                while (true)
                {
                    Console.WriteLine("Descriptor path:");
                    string descriptorPath = Console.ReadLine();
                    if (descriptorPath.Length == 0)
                        break;
                    descriptorList.Add(script.GetDescriptorByPath(descriptorPath));
                }
                submission.SetLogoDescriptors(descriptorList.ToArray());

                // Set machine dimensions
                foreach (string machineName in machines)
                {
                    IResource machine = rootPool.GetResourceByName(machineName);
                    while (true)
                    {
                        Console.WriteLine("Dimension name ({0}):", machineName);
                        string dimName = Console.ReadLine();
                        if (dimName.Length == 0)
                            break;
                        Console.WriteLine("Dimension value ({0}):", machineName);
                        machine.SetDimension(dimName, Console.ReadLine());
                    }
                    // Set the WDKSubmissionId dimension for all machines
                    machine.SetDimension("WDKSubmissionId", submission.Id.ToString() + "_" + submission.Name);
                }

                // Get job parameters
                List<string> paramNames = new List<string>();
                List<string> paramValues = new List<string>();
                foreach (string machineName in machines)
                {
                    while (true)
                    {
                        Console.WriteLine("Parameter name ({0}):", machineName);
                        string paramName = Console.ReadLine();
                        if (paramName.Length == 0)
                            break;
                        Console.WriteLine("Device regex ({0}):", machineName);
                        IDevice d = GetDevice(rootPool, machineName, Console.ReadLine());
                        if (d == null)
                            return 1;
                        string deviceName = d.GetAttribute("name")[0].ToString();
                        Console.WriteLine("Setting parameter value to '{0}'", deviceName);
                        paramNames.Add(paramName);
                        paramValues.Add(deviceName);
                    }
                }

                // Find jobs that match the requested pattern
                Console.WriteLine("Scheduling jobs:");
                List<IJob> jobs = new List<IJob>();
                foreach (IJob j in submission.GetJobs())
                {
                    if (jobRegex.IsMatch(j.Name))
                    {
                        Console.WriteLine("    " + j.Name);
                        // Set job parameters
                        for (int i = 0; i < paramNames.Count; i++)
                        {
                            IParameter p = j.GetParameterByName(paramNames[i]);
                            if (p != null)
                                p.ScheduleValue = paramValues[i];
                        }
                        jobs.Add(j);
                    }
                }
                if (jobs.Count == 0)
                {
                    Console.WriteLine("Error: no submission jobs match pattern '{0}'", jobRegex);
                    return 1;
                }

                // Create a schedule, add jobs to it and run it
                ISchedule schedule = script.CreateNewSchedule();
                foreach (IScheduleItem item in submission.ProcessJobs(jobs.ToArray()))
                {
                    item.Device = device;
                    schedule.AddScheduleItem(item);
                }
                schedule.AddSubmission(submission);
                schedule.SetResourcePool(newPool);
                script.RunSchedule(schedule);

                // Wait for jobs to complete
                Console.WriteLine("Waiting for all jobs to complete (timeout={0}s)", timeout);
                DateTime endTime = DateTime.Now.AddSeconds(timeout);
                int numCompleted, numFailed;
                do
                {
                    System.Threading.Thread.Sleep(30000);
                    // Report results in a Python readable format and count completed and failed schedule jobs
                    numCompleted = numFailed = 0;
                    Console.WriteLine();
                    Console.WriteLine("---- [");
                    foreach (IResult r in schedule.GetResults())
                    {
                        if (r.ResultStatus != "InProgress") numCompleted++;
                        if (r.ResultStatus == "Investigate") numFailed++;
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
                    }
                    Console.WriteLine("] ----");
                } while (numCompleted < schedule.GetResults().Length && DateTime.Now < endTime);

                Console.WriteLine();

                // Cancel incomplete jobs
                foreach (IResult r in schedule.GetResults())
                    if (r.ResultStatus == "InProgress")
                        r.Cancel();

                // Reset the machines
                foreach (string machineName in machines)
                    ResetMachine(rootPool, machineName, false);

                // Report failures
                if (numCompleted < schedule.GetResults().Length)
                    Console.WriteLine("Some jobs did not complete on time.");
                if (numFailed > 0)
                    Console.WriteLine("Some jobs failed.");
                if (numFailed > 0 || numCompleted < schedule.GetResults().Length)
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
