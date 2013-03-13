package autotest.afe;

import autotest.common.JSONArrayList;
import autotest.common.StaticDataRepository;
import autotest.common.Utils;
import autotest.common.table.DataTable;
import autotest.common.table.DataTable.WidgetType;
import autotest.common.table.DataTable.DataTableListener;
import autotest.common.table.DataTable.TableWidgetFactory;
import autotest.common.table.SelectionManager;
import autotest.common.table.SelectionManager.SelectionListener;
import autotest.common.table.TableClickWidget;
import autotest.common.ui.SimplifiedList;

import com.google.gwt.event.dom.client.ChangeEvent;
import com.google.gwt.event.dom.client.ChangeHandler;
import com.google.gwt.json.client.JSONArray;
import com.google.gwt.json.client.JSONObject;
import com.google.gwt.json.client.JSONValue;
import com.google.gwt.user.client.ui.Composite;
import com.google.gwt.user.client.ui.HasHTML;
import com.google.gwt.user.client.ui.Widget;

import java.util.ArrayList;
import java.util.Collection;
import java.util.HashMap;
import java.util.List;
import java.util.Map;

public class TestSelector extends Composite implements DataTableListener, ChangeHandler,
                                                TableWidgetFactory, SelectionListener {
    public static interface Display {
        public SimplifiedList getTestTypeSelect();
        public IDataTable getTestTable();
        public ISelectionManager getTestSelection();
        public HasHTML getTestInfo();
    }

    // TODO: Change DataTable to passive view, then get rid of this ad-hoc interface
    public static interface IDataTable {
        public void setWidgetFactory(TableWidgetFactory widgetFactory);
        public void addListener(DataTableListener listener);
        public void clear();
        public void addRow(JSONObject row);
        public void refreshWidgets();

        public static class DataTableImpl extends DataTable implements IDataTable {
            public DataTableImpl(String[][] columns) {
                super(columns);
            }
        }
    }

    // TODO: Change SelectionManager to use the DataTable passive view model, then get rid of this
    // ad-hoc interface
    public static interface ISelectionManager {
        public void deselectAll();
        public Widget createWidget(int row, int cell, JSONObject rowObject, WidgetType type);
        public void addListener(SelectionListener listener);

        public static class SelectionManagerImpl extends SelectionManager
                implements ISelectionManager {
            public SelectionManagerImpl(DataTable table, boolean selectOnlyOne) {
                super(table, selectOnlyOne);
            }

        }
    }

    // control file types
    public static final String SERVER_TYPE = "Server";
    public static final String CLIENT_TYPE = "Client";

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

    private boolean enabled = true;
    private TestSelectorListener listener;
    private StaticDataRepository staticData = StaticDataRepository.getRepository();
    private List<JSONObject> selectedTests = new ArrayList<JSONObject>();

    private Display display;

    public void bindDisplay(Display display) {
        this.display = display;

        display.getTestTypeSelect().addItem(CLIENT_TYPE, CLIENT_TYPE);
        display.getTestTypeSelect().addItem(SERVER_TYPE, SERVER_TYPE);
        display.getTestTypeSelect().addChangeHandler(this);

        display.getTestTable().setWidgetFactory(this);
        display.getTestTable().addListener(this);

        populateTests();

        display.getTestSelection().addListener(this);
    }

    private void populateTests() {
        display.getTestSelection().deselectAll();
        display.getTestTable().clear();

        JSONArray tests = staticData.getData("tests").isArray();
        for (JSONObject test : new JSONArrayList<JSONObject>(tests)) {
            if (!includeExperimentalTests()
                    && test.get("experimental").isBoolean().booleanValue()) {
                continue;
            }
            String testType = test.get("test_type").isString().stringValue();
            if (testType.equals(getSelectedTestType())) {
                display.getTestTable().addRow(test);
            }
        }
    }

    private boolean includeExperimentalTests() {
        JSONObject user = staticData.getData("current_user").isObject();
        return user.get("show_experimental").isBoolean().booleanValue();
    }

    @Override
    public void onRowClicked(int rowIndex, JSONObject row, boolean isRightClick) {
        TestInfoBuilder builder = new TestInfoBuilder(row);
        display.getTestInfo().setHTML(builder.getInfo());
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
        return display.getTestTypeSelect().getSelectedName();
    }

    public void setEnabled(boolean enabled) {
        this.enabled = enabled;
        display.getTestTypeSelect().setEnabled(enabled);
        display.getTestTable().refreshWidgets();
    }

    public Widget createWidget(int row, int cell, JSONObject rowObject, WidgetType type) {
        TableClickWidget widget =
            (TableClickWidget) display.getTestSelection().createWidget(row, cell, rowObject, type);
        if (!enabled) {
            widget.getContainedWidget().setEnabled(false);
        }
        return widget;
    }

    public void reset() {
        display.getTestTypeSelect().selectByName(CLIENT_TYPE);
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

    public void onClick(JSONValue id, String profile) { }
}
