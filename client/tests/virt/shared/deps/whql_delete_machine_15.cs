// DTM machine deletion tool
// Author: Michael Goldish <mgoldish@redhat.com>
// Based on sample code by Microsoft.

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
            if (args.Length != 2)
            {
                Console.WriteLine("Error: incorrect number of command line arguments");
                Console.WriteLine("Usage: {0} serverName clientName",
                    System.Environment.GetCommandLineArgs()[0]);
                return 1;
            }
            string serverName = args[0];
            string clientName = args[1];

            try
            {
                // Initialize DeviceScript and connect to data store
                Console.WriteLine("Initializing DeviceScript object");
                DeviceScript script = new DeviceScript();
                Console.WriteLine("Connecting to data store");
                script.ConnectToNamedDataStore(serverName);

                // Find the client machine
                IResourcePool rootPool = script.GetResourcePoolByName("$");
                Console.WriteLine("Looking for client machine '{0}'", clientName);
                IResource machine = rootPool.GetResourceByName(clientName);
                if (machine == null)
                {
                    Console.WriteLine("Client machine not found");
                    return 0;
                }
                Console.WriteLine("Client machine '{0}' found ({1}, {2})",
                    clientName, machine.OperatingSystem, machine.ProcessorArchitecture);

                // Change the client machine's status to 'unsafe'
                Console.WriteLine("Changing the client machine's status to 'Unsafe'");
                try
                {
                    machine.ChangeResourceStatus("Unsafe");
                }
                catch (Exception e)
                {
                    Console.WriteLine("Warning: " + e.Message);
                }
                while (machine.Status != "Unsafe")
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

                // Delete the client machine from datastore
                Console.WriteLine("Deleting client machine from data store");
                script.DeleteResource(machine.Id);
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
