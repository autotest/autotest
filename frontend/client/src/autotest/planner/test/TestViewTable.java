package autotest.planner.test;

import autotest.common.JSONArrayList;
import autotest.common.Utils;
import autotest.planner.TestPlannerTableDisplay;
import autotest.planner.TestPlannerTableDisplay.RowDisplay;

import com.google.gwt.json.client.JSONObject;
import com.google.gwt.json.client.JSONString;

import java.util.ArrayList;
import java.util.Arrays;
import java.util.List;
import java.util.Map;
import java.util.Set;
import java.util.TreeSet;

public class TestViewTable {

    private static final List<String> HEADERS = Arrays.asList(new String[] {
        "Test alias",
        "Machine status",
        "Machines passed (% of finished)",
        "Test statistics",
        "Bugs filed"
    });

    private static class Test implements Comparable<Test> {
        String alias;
        int totalMachines;
        Map<String, String> machineStatus;
        int totalRuns;
        int totalPasses;
        List<String> bugs;

        private Test(String alias, int totalMachines, Map<String, String> machineStatus,
                int totalRuns, int totalPasses, List<String> bugs) {
            this.alias = alias;
            this.totalMachines = totalMachines;
            this.machineStatus = machineStatus;
            this.totalRuns = totalRuns;
            this.totalPasses = totalPasses;
            this.bugs = bugs;
        }

        static Test fromJsonObject(String alias, JSONObject test) {
            List<String> bugs = new ArrayList<String>();
            for (JSONString bug : new JSONArrayList<JSONString>(test.get("bugs").isArray())) {
                bugs.add(Utils.jsonToString(bug));
            }

            return new Test(alias,
                    (int) test.get("total_machines").isNumber().doubleValue(),
                    Utils.jsonObjectToMap(test.get("machine_status").isObject()),
                    (int) test.get("total_runs").isNumber().doubleValue(),
                    (int) test.get("total_passes").isNumber().doubleValue(),
                    bugs);
        }

        @Override
        public int compareTo(Test o) {
            return alias.compareTo(o.alias);
        }

        @Override
        public boolean equals(Object other) {
            if (!(other instanceof Test)) {
                return false;
            }

            return alias.equals(((Test) other).alias);
        }

        @Override
        public int hashCode() {
            return alias.hashCode();
        }
    }

    private TestPlannerTableDisplay display;

    public void bindDisplay(TestPlannerTableDisplay display) {
        this.display = display;
    }

    public void setData(JSONObject data) {
        Set<Test> tests = new TreeSet<Test>();
        for (String alias : data.keySet()) {
            tests.add(Test.fromJsonObject(alias, data.get(alias).isObject()));
        }

       display.clearData();
       display.setHeaders(HEADERS);

       for (Test test : tests) {
           int running = 0;
           int finished = 0;
           int pass = 0;
           for (String status : test.machineStatus.values()) {
               if (status.equals("Running")) {
                   running++;
               } else if (status.equals("Pass")) {
                   finished++;
                   pass++;
               } else if (status.equals("Fail")) {
                   finished++;
               }
           }

           List<RowDisplay> row = new ArrayList<RowDisplay>();
           row.add(new RowDisplay(test.alias));

           String runningStr = "Running: " + Utils.numberAndPercentage(running, test.totalMachines);
           String finishedStr =
                   "Finished: " + Utils.numberAndPercentage(finished, test.totalMachines);
           row.add(new RowDisplay(runningStr + "\n" + finishedStr));

           row.add(new RowDisplay(Utils.numberAndPercentage(pass, finished)));

           String runsStr = "Runs: " + test.totalRuns;
           String passesStr =
                   "Passes: " + Utils.numberAndPercentage(test.totalPasses, test.totalRuns);
           row.add(new RowDisplay(runsStr + "\n" + passesStr));

           row.add(new RowDisplay(String.valueOf(test.bugs.size())));

           display.addRow(row);
       }

       display.finalRender();
    }
}
