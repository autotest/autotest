package autotest.planner.triage;

import autotest.common.spreadsheet.Spreadsheet;

import com.google.gwt.user.client.ui.Composite;

public class FailureTableDisplay extends Composite implements FailureTable.Display {
    
    private Spreadsheet spreadsheet = new Spreadsheet();
    
    public FailureTableDisplay() {
        initWidget(spreadsheet);
    }
    
    @Override
    public Spreadsheet getSpreadsheet() {
        return spreadsheet;
    }
    
    @Override
    public TriagePopup.Display generateTriagePopupDisplay() {
        return new TriagePopupDisplay();
    }
}
