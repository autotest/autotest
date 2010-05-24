package autotest.planner.machine;

import autotest.common.Utils;
import autotest.planner.TestPlannerTableDisplay;
import autotest.planner.TestPlannerTableDisplay.RowDisplay;

import com.google.gwt.json.client.JSONArray;
import com.google.gwt.json.client.JSONObject;

import java.util.ArrayList;
import java.util.Arrays;
import java.util.HashMap;
import java.util.List;
import java.util.Map;
import java.util.Set;
import java.util.TreeSet;

public class MachineViewTable {

    public static class Row {
        String machine;
        String status;
        Map<String, StatusSummary> statusSummaries;
        List<String> bugIds;

        private Row(String machine, String status,
                Map<String, StatusSummary> statusSummaries, List<String> bugIds) {
            this.machine = machine;
            this.status = status;
            this.statusSummaries = statusSummaries;
            this.bugIds = bugIds;
        }

        public static Row fromJsonObject(JSONObject rowObject) {
            Map<String, StatusSummary> statusSummaries = new HashMap<String, StatusSummary>();

            JSONArray testsRun = rowObject.get("tests_run").isArray();
            for (int i = 0; i < testsRun.size(); i++) {
                JSONObject test = testsRun.get(i).isObject();
                String testName = Utils.jsonToString(test.get("test_name"));

                StatusSummary statusSummary = statusSummaries.get(testName);
                if (statusSummary == null) {
                    statusSummary = new StatusSummary();
                    statusSummaries.put(testName, statusSummary);
                }

                statusSummary.addStatus(Utils.jsonToString(test.get("status")));
            }

            return new Row(Utils.jsonToString(rowObject.get("machine")),
                    Utils.jsonToString(rowObject.get("status")),
                    statusSummaries,
                    Arrays.asList(Utils.JSONtoStrings(rowObject.get("bug_ids").isArray())));
        }
    }

    private TestPlannerTableDisplay display;
    private List<Row> rows = new ArrayList<Row>();

    public void bindDisplay(TestPlannerTableDisplay display) {
        this.display = display;
    }

    public void setData(JSONArray data) {
        for (int i = 0; i < data.size(); i++) {
            rows.add(Row.fromJsonObject(data.get(i).isObject()));
        }

        display.clearData();
        displayData();
    }

    private void displayData() {
        Set<String> allTestNames = new TreeSet<String>();
        for (Row row : rows) {
            allTestNames.addAll(row.statusSummaries.keySet());
        }

        List<String> headers = new ArrayList<String>();
        headers.add("Machine");
        headers.add("Status");
        headers.addAll(allTestNames);
        headers.add("Bugs Filed");
        display.setHeaders(headers);

        for (Row row : rows) {
            List<RowDisplay> rowData = new ArrayList<RowDisplay>();
            rowData.add(new RowDisplay(row.machine));
            rowData.add(new RowDisplay(row.status));

            for (String testName : allTestNames) {
                StatusSummary statusSummary = row.statusSummaries.get(testName);
                if (statusSummary != null) {
                    rowData.add(new RowDisplay(
                            statusSummary.formatStatusCounts(), statusSummary.getCssClass()));
                } else {
                    rowData.add(new RowDisplay(""));
                }
            }

            rowData.add(new RowDisplay(String.valueOf(row.bugIds.size())));

            display.addRow(rowData);
        }

        display.finalRender();
    }
}
