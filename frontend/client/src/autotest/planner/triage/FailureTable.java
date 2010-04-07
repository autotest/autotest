package autotest.planner.triage;

import autotest.common.spreadsheet.Spreadsheet;
import autotest.common.spreadsheet.Spreadsheet.CellInfo;
import autotest.common.spreadsheet.Spreadsheet.Header;
import autotest.common.spreadsheet.Spreadsheet.HeaderImpl;
import autotest.common.spreadsheet.Spreadsheet.SpreadsheetListener;

import com.google.gwt.json.client.JSONObject;
import com.google.gwt.user.client.IncrementalCommand;

import java.util.ArrayList;
import java.util.Collections;
import java.util.LinkedList;
import java.util.List;

class FailureTable implements SpreadsheetListener {
    
    public interface Display {
        public Spreadsheet getSpreadsheet();
    }
    
    private static class Failure {
        int id;
        String machine;
        boolean blocked;
        String testName;
        String reason;
        boolean seen;
        
        private Failure(int id, String machine, boolean blocked,
                String testName, String reason, boolean seen) {
            this.id = id;
            this.machine = machine;
            this.blocked = blocked;
            this.testName = testName;
            this.reason = reason;
            this.seen = seen;
        }
        
        public static Failure fromJsonObject(JSONObject failureObj) {
            return new Failure((int) failureObj.get("id").isNumber().doubleValue(),
                failureObj.get("machine").isString().stringValue(),
                failureObj.get("blocked").isBoolean().booleanValue(),
                failureObj.get("test_name").isString().stringValue(),
                failureObj.get("reason").isString().stringValue(),
                failureObj.get("seen").isBoolean().booleanValue());
        }
    }
    
    private Display display;
    private String group;
    private LinkedList<Failure> failures = new LinkedList<Failure>();
    private boolean rendered;
    
    public FailureTable(String group) {
        this.group = group;
    }
    
    public void bindDisplay(Display display) {
        this.display = display;
    }
    
    public void addFailure(JSONObject failureObj) {
        rendered = false;
        
        Failure failure = Failure.fromJsonObject(failureObj);
        
        if (failure.seen) {
            failures.addLast(failure);
        } else {
            failures.addFirst(failure);
        }
    }
    
    public Display getDisplay() {
        if (!rendered) {
            renderDisplay();
        }
        
        return display;
    }
    
    public void renderDisplay() {
        Spreadsheet spreadsheet = display.getSpreadsheet();
        
        Header rowFields = HeaderImpl.fromBaseType(Collections.singletonList("machine"));
        Header columnFields = new HeaderImpl();
        columnFields.add("group");
        columnFields.add("failure");
        spreadsheet.setHeaderFields(rowFields, columnFields);
        
        for (int i = 0; i < failures.size(); i++) {
            Failure failure = failures.get(i);
            String machine = (i+1) + ": " + failure.machine;
            if (failure.blocked) {
                machine += " (blocked)";
            }
            spreadsheet.addRowHeader(Collections.singletonList(machine));
        }
        spreadsheet.addColumnHeader(createHeaderGroup("Test"));
        spreadsheet.addColumnHeader(createHeaderGroup("Reason"));
        
        spreadsheet.prepareForData();
        
        for (int row = 0; row < failures.size(); row++) {
            CellInfo test = spreadsheet.getCellInfo(row, 0);
            CellInfo reason = spreadsheet.getCellInfo(row, 1);
            Failure failure = failures.get(row);
            
            test.contents = failure.testName;
            reason.contents = failure.reason;
            
            if (!failure.seen) {
                test.contents = "<b>" + test.contents + "</b>";
                reason.contents = "<b>" + reason.contents + "</b>";
            }
        }
        
        spreadsheet.setVisible(true);
        
        spreadsheet.render(new IncrementalCommand() {
            @Override
            public boolean execute() {
              rendered = true;
              return false;
            }
        });
    }
    
    private List<String> createHeaderGroup(String label) {
        List<String> header = new ArrayList<String>();
        header.add(group);
        header.add(label);
        return header;
    }

    @Override
    public void onCellClicked(CellInfo cellInfo, boolean isRightClick) {
        //TODO: handle row clicks (pop up the triage panel)
    }
}
