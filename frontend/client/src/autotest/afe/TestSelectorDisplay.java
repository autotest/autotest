package autotest.afe;

import autotest.afe.TestSelector.IDataTable;
import autotest.afe.TestSelector.IDataTable.DataTableImpl;
import autotest.afe.TestSelector.ISelectionManager;
import autotest.afe.TestSelector.ISelectionManager.SelectionManagerImpl;
import autotest.common.table.DataTable;
import autotest.common.ui.ExtendedListBox;
import autotest.common.ui.SimplifiedList;

import com.google.gwt.user.client.ui.Composite;
import com.google.gwt.user.client.ui.HTML;
import com.google.gwt.user.client.ui.HasHTML;
import com.google.gwt.user.client.ui.HorizontalPanel;
import com.google.gwt.user.client.ui.HorizontalSplitPanel;
import com.google.gwt.user.client.ui.Label;
import com.google.gwt.user.client.ui.Panel;
import com.google.gwt.user.client.ui.VerticalPanel;

public class TestSelectorDisplay extends Composite implements TestSelector.Display {
    private static final String[][] testTableColumns = new String[][] {
        {DataTable.WIDGET_COLUMN, ""},
        {"name", "Test"},
    };

    private ExtendedListBox testTypeSelect = new ExtendedListBox();
    private DataTableImpl testTable = new DataTableImpl(testTableColumns);
    private SelectionManagerImpl testSelection = new SelectionManagerImpl(testTable, false);
    private HTML testInfo = new HTML("Click a test to view its description");
    private HorizontalSplitPanel mainPanel = new HorizontalSplitPanel();

    public TestSelectorDisplay() {
        testInfo.setStyleName("test-description");

        testTable.fillParent();
        testTable.setClickable(true);

        Panel testTypePanel = new HorizontalPanel();
        testTypePanel.add(new Label("Test type:"));
        testTypePanel.add(testTypeSelect);

        Panel testInfoPanel = new VerticalPanel();
        testInfoPanel.add(testInfo);

        mainPanel.setLeftWidget(testTable);
        mainPanel.setRightWidget(testInfoPanel);
        mainPanel.setSize("100%", "30em");
        mainPanel.setSplitPosition("20em");

        Panel container = new VerticalPanel();
        container.add(testTypePanel);
        container.add(mainPanel);
        container.setWidth("100%");

        initWidget(container);
    }

    public SimplifiedList getTestTypeSelect() {
        return testTypeSelect;
    }

    public HasHTML getTestInfo() {
        return testInfo;
    }

    public ISelectionManager getTestSelection() {
        return testSelection;
    }

    public IDataTable getTestTable() {
        return testTable;
    }
}
