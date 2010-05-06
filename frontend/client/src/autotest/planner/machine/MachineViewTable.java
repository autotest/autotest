package autotest.planner.machine;

import autotest.common.Utils;

import com.google.gwt.json.client.JSONArray;
import com.google.gwt.json.client.JSONObject;

import java.util.ArrayList;
import java.util.Arrays;
import java.util.Collection;
import java.util.HashMap;
import java.util.List;
import java.util.Map;
import java.util.Set;
import java.util.TreeSet;

public class MachineViewTable {

    public static class PassRate {
        int passed;
        int total;
    }

    public static class Row {
        String machine;
        String status;
        Map<String, PassRate> passRates;
        List<String> bugIds;

        private Row(String machine, String status,
                Map<String, PassRate> passRates, List<String> bugIds) {
            this.machine = machine;
            this.status = status;
            this.passRates = passRates;
            this.bugIds = bugIds;
        }

        public static Row fromJsonObject(JSONObject rowObject) {
            Map<String, PassRate> passRates = new HashMap<String, PassRate>();

            JSONArray testsRun = rowObject.get("tests_run").isArray();
            for (int i = 0; i < testsRun.size(); i++) {
                JSONObject test = testsRun.get(i).isObject();
                String testName = Utils.jsonToString(test.get("test_name"));

                PassRate passRate = passRates.get(testName);
                if (passRate == null) {
                    passRate = new PassRate();
                    passRates.put(testName, passRate);
                }

                passRate.total++;
                if (test.get("success").isBoolean().booleanValue()) {
                    passRate.passed++;
                }
            }

            return new Row(Utils.jsonToString(rowObject.get("machine")),
                    Utils.jsonToString(rowObject.get("status")),
                    passRates,
                    Arrays.asList(Utils.JSONtoStrings(rowObject.get("bug_ids").isArray())));
        }
    }

    public static interface Display {
        public void clearData();
        public void setHeaders(Collection<String> headers);
        public void addRow(Collection<String> rowData);
        public void finalRender();
    }

    private Display display;
    private List<Row> rows = new ArrayList<Row>();

    public void bindDisplay(Display display) {
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
            allTestNames.addAll(row.passRates.keySet());
        }

        List<String> headers = new ArrayList<String>();
        headers.add("Machine");
        headers.add("Status");
        headers.addAll(allTestNames);
        headers.add("Bugs Filed");
        display.setHeaders(headers);

        for (Row row : rows) {
            List<String> rowData = new ArrayList<String>();
            rowData.add(row.machine);
            rowData.add(row.status);

            for (String testName : allTestNames) {
                PassRate passRate = row.passRates.get(testName);
                if (passRate != null) {
                    rowData.add(passRate.passed + "/" + passRate.total);
                } else {
                    rowData.add("");
                }
            }

            rowData.add(String.valueOf(row.bugIds.size()));

            display.addRow(rowData);
        }

        display.finalRender();
    }
}
