package autotest.planner.overview;

import autotest.common.JSONArrayList;
import autotest.common.StaticDataRepository;
import autotest.common.Utils;
import autotest.common.Utils.JsonObjectFactory;

import com.google.gwt.json.client.JSONArray;
import com.google.gwt.json.client.JSONObject;
import com.google.gwt.json.client.JSONString;
import com.google.gwt.json.client.JSONValue;

import java.util.ArrayList;
import java.util.Arrays;
import java.util.HashMap;
import java.util.List;
import java.util.Map;

public class OverviewTable {
    public static interface Display {
        public void addHeaderGroup(String group, String[] headers);
        public void clearAllData();
        public void addData(String header, List<String> data);
    }

    private static class Machine {
        static JsonObjectFactory<Machine> FACTORY = new JsonObjectFactory<Machine>() {
            public Machine fromJsonObject(JSONObject object) {
                return Machine.fromJsonObject(object);
            }
        };

        @SuppressWarnings("unused")     // Will be needed later for drilldowns
        String hostname;

        Boolean passed;
        String status;

        private Machine(String hostname, Boolean passed, String status) {
            this.hostname = hostname;
            this.passed = passed;
            this.status = status;
        }

        private static Machine fromJsonObject(JSONObject machine) {
            Boolean passed = null;
            JSONValue passedJson = machine.get("passed");
            if (passedJson.isNull() == null) {
                passed = passedJson.isBoolean().booleanValue();
            }

            return new Machine(Utils.jsonToString(machine.get("hostname")),
                    passed,
                    Utils.jsonToString(machine.get("status")));
        }
    }

    private static class TestConfig {
        static JsonObjectFactory<TestConfig> FACTORY = new JsonObjectFactory<TestConfig>() {
            public TestConfig fromJsonObject(JSONObject object) {
                return TestConfig.fromJsonObject(object);
            }
        };

        int complete;
        int estimatedRuntime;

        private TestConfig(int complete, int estimatedRuntime) {
            this.complete = complete;
            this.estimatedRuntime = estimatedRuntime;
        }

        private static TestConfig fromJsonObject(JSONObject testConfig) {
            return new TestConfig((int) testConfig.get("complete").isNumber().doubleValue(),
                    (int) testConfig.get("estimated_runtime").isNumber().doubleValue());
        }
    }

    private static class PlanData {
        List<Machine> machines;
        List<String> bugs;
        List<TestConfig> testConfigs;

        private PlanData(List<Machine> machines, List<String> bugs, List<TestConfig> testConfigs) {
            this.machines = machines;
            this.bugs = bugs;
            this.testConfigs = testConfigs;
        }

        static PlanData fromJsonObject(JSONObject planData) {
            JSONArray machinesJson = planData.get("machines").isArray();
            List<Machine> machines = Utils.createList(machinesJson, Machine.FACTORY);

            JSONArray bugsJson = planData.get("bugs").isArray();
            List<String> bugs = Arrays.asList(Utils.JSONtoStrings(bugsJson));

            JSONArray testConfigsJson = planData.get("test_configs").isArray();
            List<TestConfig> testConfigs =
                    Utils.createList(testConfigsJson, TestConfig.FACTORY);

            return new PlanData(machines, bugs, testConfigs);
        }
    }

    private Display display;
    private List<String> statuses = new ArrayList<String>();

    public void bindDisplay(Display display) {
        this.display = display;
        setupDisplay();
    }

    private void setupDisplay() {
        List<String> hostStatuses = new ArrayList<String>();
        JSONArrayList<JSONString> hostStatusesArray = new JSONArrayList<JSONString>(
                StaticDataRepository.getRepository().getData("host_statuses").isArray());
        for (JSONString status : hostStatusesArray) {
            String statusStr = Utils.jsonToString(status);
            hostStatuses.add(statusStr);
            statuses.add(statusStr);
        }

        display.addHeaderGroup("Basic info",
                new String[] {"Total machines", "Progress", "Bugs filed"});
        display.addHeaderGroup("Machine status",
                hostStatuses.toArray(new String[hostStatuses.size()]));
        display.addHeaderGroup("Pass rate",
                new String[] {"Passed", "Failed"});
        display.addHeaderGroup("Plan statistics",
                new String[] {"Tests run", "Tests remaining"});
    }

    public void setData(Map<String, JSONObject> data) {
        display.clearAllData();
        for (Map.Entry<String, JSONObject> entry : data.entrySet()) {
            PlanData planData = PlanData.fromJsonObject(entry.getValue());

            int total = planData.machines.size();
            String totalStr = String.valueOf(total);

            int runNumber = 0;
            int runHours = 0;
            int remainingNumber = 0;
            int remainingHours = 0;

            for (TestConfig config : planData.testConfigs) {
                int remaining = total - config.complete;

                runNumber += config.complete;
                remainingNumber += remaining;
                runHours += config.complete * config.estimatedRuntime;
                remainingHours += remaining * config.estimatedRuntime;
            }

            String progress = Utils.percentage(runHours, runHours + remainingHours);
            String bugs = String.valueOf(planData.bugs.size());

            int passed = 0;
            int passFailTotal = 0;
            Map<String, Integer> statusCounts = new HashMap<String, Integer>();
            for (String status : statuses) {
                statusCounts.put(status, 0);
            }
            for (Machine machine : planData.machines) {
                statusCounts.put(machine.status, statusCounts.get(machine.status) + 1);

                if (machine.passed != null) {
                    passFailTotal++;
                    if (machine.passed) {
                        passed++;
                    }
                }
            }

            List<String> displayData = new ArrayList<String>();
            displayData.add(totalStr);
            displayData.add(progress);
            displayData.add(bugs);
            for (String status : statuses) {
                displayData.add(Utils.numberAndPercentage(statusCounts.get(status), total));
            }
            displayData.add(Utils.numberAndPercentage(passed, passFailTotal));
            displayData.add(Utils.numberAndPercentage(passFailTotal - passed, passFailTotal));
            displayData.add(runNumber + " (" + runHours + " hours)");
            displayData.add(remainingNumber + " (" + remainingHours + " hours)");

            display.addData(entry.getKey(), displayData);
        }
    }
}
