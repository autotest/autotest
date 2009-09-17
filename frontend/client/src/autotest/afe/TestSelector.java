package autotest.afe;

import autotest.common.JSONArrayList;
import autotest.common.StaticDataRepository;
import autotest.common.Utils;
import autotest.common.table.DataTable;
import autotest.common.table.SelectionManager;
import autotest.common.table.TableClickWidget;
import autotest.common.table.DataTable.DataTableListener;
import autotest.common.table.DataTable.TableWidgetFactory;
import autotest.common.table.SelectionManager.SelectionListener;

import com.google.gwt.event.dom.client.ChangeEvent;
import com.google.gwt.event.dom.client.ChangeHandler;
import com.google.gwt.json.client.JSONArray;
import com.google.gwt.json.client.JSONObject;
import com.google.gwt.user.client.ui.Composite;
import com.google.gwt.user.client.ui.HTML;
import com.google.gwt.user.client.ui.HorizontalPanel;
import com.google.gwt.user.client.ui.HorizontalSplitPanel;
import com.google.gwt.user.client.ui.Label;
import com.google.gwt.user.client.ui.ListBox;
import com.google.gwt.user.client.ui.Panel;
import com.google.gwt.user.client.ui.VerticalPanel;
import com.google.gwt.user.client.ui.Widget;

import java.util.ArrayList;
import java.util.Collection;
import java.util.HashMap;
import java.util.List;
import java.util.Map;

class TestSelector extends Composite implements DataTableListener, ChangeHandler, 
                                                TableWidgetFactory, SelectionListener {
    // control file types
    static final String SERVER_TYPE = "Server";
    static final String CLIENT_TYPE = "Client";
    
    private static final String[][] testTableColumns = new String[][] {
        {DataTable.WIDGET_COLUMN, ""},
        {"name", "Test"},
    };
    
    public static interface TestSelectorListener {
        /**
         * Called when a test is selected or deselected, or when the test type is changed.
         */
        public void onTestSelectionChanged();
    }
    
    private static class TestInfoBuilder {
        private static final Map<String, String> timeMap = new HashMap<String, String>();
        static {
            timeMap.put("SHORT", "less than 15 minutes");
            timeMap.put("MEDIUM", "15 minutes to four hours");
            timeMap.put("LONG", "over four hours");
        }
        
        private StringBuilder builder = new StringBuilder();
        private JSONObject test;
        
        public TestInfoBuilder(JSONObject test) {
            this.test = test;
            
            writeTitleLine();
            appendTextField("Written by", getField("author"));
            appendTextField("Type", getField("test_type"));
            appendTextField("Synchronization count", getField("sync_count"));
            writeTime();
            writeSkipVerify(test);
            
            builder.append("<br>" + getField("description"));
        }

        private void writeTitleLine() {
            builder.append("<b>" + getField("name") + "</b> ");
            builder.append("(" + 
                           getField("test_class") + " / " + getField("test_category") + 
                           ")<br><br>");
        }
        
        private void writeTime() {
            String time = getField("test_time");
            String timeDetail = "unknown time";
            if (timeMap.containsKey(time)) {
                timeDetail = timeMap.get(time);
            }
            appendTextField("Time", time + " (" + timeDetail + ")");
        }

        private void writeSkipVerify(JSONObject test) {
            if (!test.get("run_verify").isBoolean().booleanValue()) {
                builder.append("Verify is <b>not</b> run<br>");
            }
        }

        private void appendTextField(String name, String text) {
            builder.append("<b>" + name + "</b>: " + text + "<br>");
        }

        private String getField(String field) {
            return Utils.escape(Utils.jsonToString(test.get(field)));
        }
        
        public String getInfo() {
            return builder.toString();
        }
    }
    
    private ListBox testTypeSelect = new ListBox();
    private DataTable testTable = new DataTable(testTableColumns);
    private SelectionManager testSelection = new SelectionManager(testTable, false);
    private HTML testInfo = new HTML("Click a test to view its description");
    private HorizontalSplitPanel mainPanel = new HorizontalSplitPanel();
    private boolean enabled = true;
    private TestSelectorListener listener;
    private StaticDataRepository staticData = StaticDataRepository.getRepository();
    private List<JSONObject> selectedTests = new ArrayList<JSONObject>();
    
    public TestSelector() {
        testInfo.setStyleName("test-description");
        
        testTypeSelect.addItem(CLIENT_TYPE);
        testTypeSelect.addItem(SERVER_TYPE);
        testTypeSelect.addChangeHandler(this);
        
        testTable.fillParent();
        testTable.setWidgetFactory(this);
        testTable.setClickable(true);
        testTable.addListener(this);
        
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
        
        populateTests();
        
        initWidget(container);
        
        testSelection.addListener(this);
    }
    
    private void populateTests() {
        testSelection.deselectAll();
        testTable.clear();
        
        JSONArray tests = staticData.getData("tests").isArray();
        for (JSONObject test : new JSONArrayList<JSONObject>(tests)) {
            if (!includeExperimentalTests() 
                    && test.get("experimental").isBoolean().booleanValue()) {
                continue;
            }
            String testType = test.get("test_type").isString().stringValue();
            if (testType.equals(getSelectedTestType())) {
                testTable.addRow(test);
            }
        }
    }

    private boolean includeExperimentalTests() {
        JSONObject user = staticData.getData("current_user").isObject();
        return user.get("show_experimental").isBoolean().booleanValue();
    }

    public void onRowClicked(int rowIndex, JSONObject row) {
        TestInfoBuilder builder = new TestInfoBuilder(row);
        testInfo.setHTML(builder.getInfo());
    }
    
    @Override
    public void onChange(ChangeEvent event) {
        populateTests();
        notifyListener();
    }
    
    public Collection<JSONObject> getSelectedTests() {
        return selectedTests;
    }

    public String getSelectedTestType() {
        return testTypeSelect.getItemText(testTypeSelect.getSelectedIndex());
    }

    public void setEnabled(boolean enabled) {
        this.enabled = enabled;
        testTypeSelect.setEnabled(enabled);
        testTable.refreshWidgets();
    }

    public Widget createWidget(int row, int cell, JSONObject rowObject) {
        TableClickWidget widget = 
            (TableClickWidget) testSelection.createWidget(row, cell, rowObject);
        if (!enabled) {
            widget.getContainedWidget().setEnabled(false);
        }
        return widget;
    }

    public void reset() {
        testTypeSelect.setSelectedIndex(0);
        populateTests();
    }
    
    private void notifyListener() {
        if (listener != null) {
            listener.onTestSelectionChanged();
        }
    }

    public void setListener(TestSelectorListener listener) {
        this.listener = listener;
    }

    public void onAdd(Collection<JSONObject> objects) {
        selectedTests.addAll(objects);
        notifyListener();
    }

    public void onRemove(Collection<JSONObject> objects) {
        selectedTests.removeAll(objects);
        notifyListener();
    }
}
