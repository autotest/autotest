package autotest.planner.triage;

import autotest.common.ui.ExtendedListBox;
import autotest.common.ui.SimplifiedList;
import autotest.planner.resources.PlannerClientBundle;

import com.google.gwt.event.dom.client.HasClickHandlers;
import com.google.gwt.user.client.ui.Button;
import com.google.gwt.user.client.ui.CheckBox;
import com.google.gwt.user.client.ui.FlexTable;
import com.google.gwt.user.client.ui.HasHorizontalAlignment;
import com.google.gwt.user.client.ui.HasText;
import com.google.gwt.user.client.ui.HasValue;
import com.google.gwt.user.client.ui.HorizontalPanel;
import com.google.gwt.user.client.ui.Image;
import com.google.gwt.user.client.ui.Panel;
import com.google.gwt.user.client.ui.PopupPanel;
import com.google.gwt.user.client.ui.TextArea;
import com.google.gwt.user.client.ui.TextBox;
import com.google.gwt.user.client.ui.VerticalPanel;
import com.google.gwt.user.client.ui.Widget;

public class TriagePopupDisplay extends PopupPanel implements TriagePopup.Display {
    private Panel container = new VerticalPanel();
    private Image closeX = new Image(PlannerClientBundle.INSTANCE.close().getURL());
    private TextBox labels = new TextBox();
    private TextArea keyvals = new TextArea();
    private TextBox bugs = new TextBox();
    private TextBox reason = new TextBox();
    private ExtendedListBox hostAction = new ExtendedListBox();
    private ExtendedListBox testAction = new ExtendedListBox();
    private CheckBox invalidate = new CheckBox("Invalidate Test");
    private Button apply = new Button("Apply");

    public TriagePopupDisplay() {
        super(false, true);
        super.setGlassEnabled(true);

        HorizontalPanel topPanel = new HorizontalPanel();
        topPanel.setWidth("100%");
        topPanel.setHorizontalAlignment(HasHorizontalAlignment.ALIGN_RIGHT);
        topPanel.add(closeX);
        container.add(topPanel);

        FlexTable bottomTable = new FlexTable();
        addRow(bottomTable, "Labels", labels);
        addRow(bottomTable, "Keyvals", keyvals);
        addRow(bottomTable, "Bugs", bugs);
        addRow(bottomTable, "Reason", reason);
        addRow(bottomTable, "Host", hostAction);
        addRow(bottomTable, "Test", testAction);
        addRow(bottomTable, null, invalidate);
        container.add(bottomTable);

        container.add(apply);

        setWidget(container);
    }

    private void addRow(FlexTable table, String label, Widget field) {
        int row = table.getRowCount();
        if (label != null) {
            table.setText(row, 0, label + ":");
        }
        table.setWidget(row, 1, field);
    }

    @Override
    public HasClickHandlers getApplyButton() {
      return apply;
    }

    @Override
    public HasText getBugsField() {
      return bugs;
    }

    @Override
    public HasClickHandlers getCloseButton() {
      return closeX;
    }

    @Override
    public SimplifiedList getHostActionField() {
      return hostAction;
    }

    @Override
    public HasValue<Boolean> getInvalidateField() {
      return invalidate;
    }

    @Override
    public HasText getKeyvalsField() {
      return keyvals;
    }

    @Override
    public HasText getLabelsField() {
      return labels;
    }

    @Override
    public HasText getReasonField() {
      return reason;
    }

    @Override
    public SimplifiedList getTestActionField() {
      return testAction;
    }
}
