package autotest.planner.overview;

import autotest.common.ui.NotifyManager;
import autotest.planner.TestPlannerDisplay;

import com.google.gwt.event.dom.client.HasClickHandlers;
import com.google.gwt.event.dom.client.HasKeyPressHandlers;
import com.google.gwt.user.client.ui.Button;
import com.google.gwt.user.client.ui.HTMLPanel;
import com.google.gwt.user.client.ui.HasText;
import com.google.gwt.user.client.ui.HasVerticalAlignment;
import com.google.gwt.user.client.ui.HorizontalPanel;
import com.google.gwt.user.client.ui.Label;
import com.google.gwt.user.client.ui.Panel;
import com.google.gwt.user.client.ui.SimplePanel;
import com.google.gwt.user.client.ui.TextBox;

public class OverviewTabDisplay implements TestPlannerDisplay, OverviewTabPresenter.Display {
    Label addPlanLabel = new Label("Add test plan:");
    TextBox addPlanField = new TextBox();
    Button addPlanButton = new Button("add");
    Panel overviewTablePanel = new SimplePanel();

    @Override
    public void initialize(HTMLPanel htmlPanel) {
        HorizontalPanel addPlanContainer = new HorizontalPanel();
        addPlanContainer.setVerticalAlignment(HasVerticalAlignment.ALIGN_MIDDLE);
        addPlanContainer.setSpacing(2);
        addPlanContainer.add(addPlanLabel);
        addPlanContainer.add(addPlanField);
        addPlanContainer.add(addPlanButton);

        htmlPanel.add(addPlanContainer, "overview_add_plan");
        htmlPanel.add(overviewTablePanel, "overview_table");
    }

    @Override
    public HasClickHandlers getAddPlanButton() {
        return addPlanButton;
    }

    @Override
    public HasKeyPressHandlers getAddPlanField() {
        return addPlanField;
    }

    @Override
    public HasText getAddPlanText() {
        return addPlanField;
    }

    @Override
    public OverviewTable.Display generateOverviewTableDisplay() {
        OverviewTableDisplay display = new OverviewTableDisplay();
        overviewTablePanel.clear();
        overviewTablePanel.add(display);
        return display;
    }

    @Override
    public void setLoading(boolean loading) {
        NotifyManager.getInstance().setLoading(loading);
    }
}
