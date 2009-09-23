package autotest.afe;

import autotest.common.ui.ExtendedListBox;
import autotest.common.ui.SimplifiedList;

import com.google.gwt.event.dom.client.HasClickHandlers;
import com.google.gwt.user.client.ui.Button;
import com.google.gwt.user.client.ui.CheckBox;
import com.google.gwt.user.client.ui.Composite;
import com.google.gwt.user.client.ui.HasText;
import com.google.gwt.user.client.ui.HasValue;
import com.google.gwt.user.client.ui.HorizontalPanel;
import com.google.gwt.user.client.ui.Label;
import com.google.gwt.user.client.ui.Panel;
import com.google.gwt.user.client.ui.SimplePanel;
import com.google.gwt.user.client.ui.TabPanel;
import com.google.gwt.user.client.ui.TextArea;
import com.google.gwt.user.client.ui.TextBox;
import com.google.gwt.user.client.ui.VerticalPanel;
import com.google.gwt.user.client.ui.Widget;

public class HostSelectorDisplay extends Composite implements HostSelector.Display {
    private TextArea hostnameInput = new TextArea();
    private Button addByHostnameButton = new Button();
    private CheckBox allowOneTimeHostsBox = new CheckBox();
    private ExtendedListBox labelList = new ExtendedListBox();
    private TextBox labelNumberInput = new TextBox();
    private Button addByLabelButton = new Button();
    private Panel availableTablePanel, selectedTablePanel;
    private TabPanel tabPanel = new TabPanel();

    private boolean haveTables = false;

    public HostSelectorDisplay() {
        // available host table
        availableTablePanel = new SimplePanel();
        tabPanel.add(availableTablePanel, "Browse hosts");

        // choose by hostname
        Panel hostnamePanel = new VerticalPanel();
        hostnamePanel.add(new Label("Enter hostnames, separated by commas or spaces"));
        hostnamePanel.add(hostnameInput);
        hostnameInput.setSize("100%", "10em");
        addByHostnameButton.setText("Select hosts");
        allowOneTimeHostsBox.setText("Allow hosts not in Autotest");
        Panel lowerPanel = new HorizontalPanel();
        lowerPanel.add(addByHostnameButton);
        lowerPanel.add(allowOneTimeHostsBox);
        hostnamePanel.add(lowerPanel);
        tabPanel.add(hostnamePanel, "Specify hostnames");

        // add metahosts
        Panel labelPanel = new VerticalPanel();
        Panel labelTop = new HorizontalPanel();
        labelTop.add(new Label("Run on any hosts with label"));
        labelTop.add(labelList);
        labelPanel.add(labelTop);
        Panel labelBottom = new HorizontalPanel();
        labelBottom.add(new Label("Number of hosts:"));
        labelBottom.add(labelNumberInput);
        labelNumberInput.setVisibleLength(4);
        addByLabelButton.setText("Add hosts");
        labelBottom.add(addByLabelButton);
        labelPanel.add(labelBottom);
        tabPanel.add(labelPanel, "Specify host labels");

        tabPanel.selectTab(0);

        // the tabbed selector is displayed alongside the list of selected hosts
        selectedTablePanel = new VerticalPanel();
        selectedTablePanel.addStyleName("box");
        Label selectedTitle = new Label("Selected hosts");
        selectedTitle.addStyleName("field-name");
        selectedTablePanel.add(selectedTitle);
        Panel outerPanel = new HorizontalPanel();
        outerPanel.add(tabPanel);
        outerPanel.add(selectedTablePanel);
        initWidget(outerPanel);
    }

    @Override
    public void addTables(Widget availableTable, Widget selectedTable) {
        assert !haveTables;
        availableTablePanel.add(availableTable);
        selectedTablePanel.add(selectedTable);
        haveTables = true;
    }

    @Override
    public HasClickHandlers getAddByHostnameButton() {
        return addByHostnameButton;
    }

    @Override
    public HasValue<Boolean> getAllowOneTimeHostsField() {
        return allowOneTimeHostsBox;
    }

    @Override
    public HasClickHandlers getAddByLabelButton() {
        return addByLabelButton;
    }

    @Override
    public HasText getHostnameField() {
        return hostnameInput;
    }

    @Override
    public SimplifiedList getLabelList() {
        return labelList;
    }

    @Override
    public HasText getLabelNumberField() {
        return labelNumberInput;
    }
}
