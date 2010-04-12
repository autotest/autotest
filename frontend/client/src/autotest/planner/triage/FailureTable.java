package autotest.planner.triage;

import autotest.common.spreadsheet.Spreadsheet;
import autotest.common.spreadsheet.Spreadsheet.CellInfo;
import autotest.common.spreadsheet.Spreadsheet.Header;
import autotest.common.spreadsheet.Spreadsheet.HeaderImpl;
import autotest.common.spreadsheet.Spreadsheet.SpreadsheetListener;
import autotest.common.ui.NotifyManager;

import com.google.gwt.json.client.JSONObject;
import com.google.gwt.user.client.IncrementalCommand;

import java.util.ArrayList;
import java.util.Collections;
import java.util.Iterator;
import java.util.LinkedList;
import java.util.List;

class FailureTable implements SpreadsheetListener, TriagePopup.Listener {
    
    public interface Display {
        public Spreadsheet getSpreadsheet();
        public TriagePopup.Display generateTriagePopupDisplay();
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
        display.getSpreadsheet().setListener(this);
    }
    
    public void addFailure(JSONObject failureObj) {
        setRendered(false);
        
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
    
    private void setRendered(boolean rendered) {
        this.rendered = rendered;
        display.getSpreadsheet().setVisible(rendered);
    }
    
    public void renderDisplay() {
        Spreadsheet spreadsheet = display.getSpreadsheet();
        spreadsheet.clear();
        
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
            test.testIndex = failure.id;
            reason.testIndex = failure.id;
            
            if (!failure.seen) {
                test.contents = "<b>" + test.contents + "</b>";
                reason.contents = "<b>" + reason.contents + "</b>";
            }
        }
        
        spreadsheet.setVisible(true);
        
        spreadsheet.render(new IncrementalCommand() {
            @Override
            public boolean execute() {
                setRendered(true);
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
        if (cellInfo.testIndex == 0) {
            return;
        }
        
        TriagePopup popup = new TriagePopup(this, cellInfo.testIndex);
        popup.bindDisplay(display.generateTriagePopupDisplay());
        popup.render();
    }

    @Override
    public void onTriage(TriagePopup source) {
        if (removeFailure(source.getId())) {
            if (!failures.isEmpty()) {
                // If no more failures, leave the spreadsheet invisible
                renderDisplay();
            }
        }
    }
    
    private boolean removeFailure(int id) {
        setRendered(false);
        
        Iterator<Failure> iter = failures.iterator();
        while (iter.hasNext()) {
            if (iter.next().id == id) {
                iter.remove();
                return true;
            }
        }
        
        /*
         * TODO: throw an Exception instead, and register a handler with
         * GWT.setUncaughtExceptionHandler()
         */
        NotifyManager.getInstance().showError("Did not find failure id " + id);
        setRendered(true);
        return false;
    }
}
