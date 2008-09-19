package autotest.tko;

import autotest.common.Utils;
import autotest.common.table.DataTable;
import autotest.common.table.DynamicTable;
import autotest.common.table.RpcDataSource;
import autotest.common.table.SelectionManager;
import autotest.common.table.SimpleFilter;
import autotest.common.table.TableDecorator;
import autotest.common.table.DataSource.SortDirection;
import autotest.common.table.DataSource.SortSpec;
import autotest.common.table.DataTable.TableWidgetFactory;
import autotest.common.table.DynamicTable.DynamicTableListener;
import autotest.common.table.SelectionManager.SelectionListener;
import autotest.common.ui.ContextMenu;
import autotest.common.ui.DoubleListSelector;
import autotest.common.ui.NotifyManager;
import autotest.common.ui.RightClickTable;
import autotest.common.ui.TableActionsPanel;
import autotest.common.ui.DoubleListSelector.Item;
import autotest.common.ui.TableActionsPanel.TableActionsListener;
import autotest.tko.CommonPanel.CommonPanelListener;
import autotest.tko.TkoUtils.FieldInfo;

import com.google.gwt.json.client.JSONObject;
import com.google.gwt.user.client.Command;
import com.google.gwt.user.client.Event;
import com.google.gwt.user.client.ui.Button;
import com.google.gwt.user.client.ui.CheckBox;
import com.google.gwt.user.client.ui.ClickListener;
import com.google.gwt.user.client.ui.HTML;
import com.google.gwt.user.client.ui.Panel;
import com.google.gwt.user.client.ui.RootPanel;
import com.google.gwt.user.client.ui.SimplePanel;
import com.google.gwt.user.client.ui.VerticalPanel;
import com.google.gwt.user.client.ui.Widget;

import java.util.ArrayList;
import java.util.Arrays;
import java.util.Collection;
import java.util.HashMap;
import java.util.Iterator;
import java.util.List;
import java.util.ListIterator;
import java.util.Map;

public class TableView extends ConditionTabView 
                       implements DynamicTableListener, TableActionsListener, SelectionListener,
                                  ClickListener, TableWidgetFactory, CommonPanelListener {
    private static final int ROWS_PER_PAGE = 30;
    private static final String[] DEFAULT_COLUMNS = 
        {"test_idx", "test_name", "job_tag", "hostname", "status"};
    private static final String[] TRIAGE_GROUP_COLUMNS =
        {"test_name", "status", "reason"};
    private static final String[] PASS_RATE_GROUP_COLUMNS =
        {"hostname"};
    private static final SortSpec[] TRIAGE_SORT_SPECS = {
        new SortSpec("test_name", SortDirection.ASCENDING),
        new SortSpec("status", SortDirection.ASCENDING),
        new SortSpec("reason", SortDirection.ASCENDING),
    };
    private static final SortSpec[] PASS_RATE_SORT_SPECS = {
        new SortSpec("test_name", SortDirection.ASCENDING)
    };
    private static final String COUNT_NAME = "Count in group";
    private static final String STATUS_COUNTS_NAME = "Test pass rate";

    private TestSelectionListener listener;
    
    private DynamicTable table;
    private TableDecorator tableDecorator;
    private SelectionManager selectionManager;
    private SimpleFilter sqlConditionFilter = new SimpleFilter();
    private RpcDataSource testDataSource = new TestViewDataSource();
    private TestGroupDataSource groupDataSource = TestGroupDataSource.getTestGroupDataSource();
    private DoubleListSelector columnSelect = new DoubleListSelector();
    private CheckBox groupCheckbox = new CheckBox("Group by these columns and show counts");
    private CheckBox statusGroupCheckbox = 
        new CheckBox("Group by these columns and show pass rates");
    private TableActionsPanel actionsPanel = new TableActionsPanel(this, true);
    private Button queryButton = new Button("Query");
    
    private boolean isTestGroupingEnabled = false, isStatusCountEnabled = false;
    private List<String> fields = new ArrayList<String>();
    private List<SortSpec> tableSorts = new ArrayList<SortSpec>();
    private Map<String, String> fieldNames = new HashMap<String, String>();
    
    public enum TableViewConfig {
        DEFAULT, PASS_RATE, TRIAGE
    }
    
    public static interface TableSwitchListener extends TestSelectionListener {
        public void onSwitchToTable(TableViewConfig config);
    }
    
    public TableView(TestSelectionListener listener) {
        this.listener = listener;
        commonPanel.addListener(this);
    }

    @Override
    public String getElementId() {
        return "table_view";
    }

    @Override
    public void initialize() {
        for (FieldInfo fieldInfo : TkoUtils.getFieldList("all_fields")) {
            fieldNames.put(fieldInfo.field, fieldInfo.name);
            columnSelect.addItem(fieldInfo.name, fieldInfo.field);
        }
        fieldNames.put(TestGroupDataSource.GROUP_COUNT_FIELD, COUNT_NAME);
        fieldNames.put(DataTable.WIDGET_COLUMN, STATUS_COUNTS_NAME);
        
        selectColumns(DEFAULT_COLUMNS);
        saveOptions(false);
        
        queryButton.addClickListener(this);
        groupCheckbox.addClickListener(this);
        statusGroupCheckbox.addClickListener(this);
        
        Panel columnPanel = new VerticalPanel();
        columnPanel.add(columnSelect);
        columnPanel.add(groupCheckbox);
        columnPanel.add(statusGroupCheckbox);
        
        RootPanel.get("table_column_select").add(columnPanel);
        RootPanel.get("table_actions").add(actionsPanel);
        RootPanel.get("table_query_controls").add(queryButton);
    }

    private void selectColumns(String[] columns) {
        columnSelect.deselectAll();
        for(String field : columns) {
            columnSelect.selectItemByValue(field);
        }
    }
    
    public void setupDefaultView() {
        selectColumns(DEFAULT_COLUMNS);
        statusGroupCheckbox.setChecked(false);
        groupCheckbox.setChecked(false);
        updateCheckboxes();
        tableSorts.clear();
    }
    
    public void setupJobTriage() {
        // easier if we ensure it's deselected and then select it
        selectColumns(TRIAGE_GROUP_COLUMNS);
        statusGroupCheckbox.setChecked(false);
        groupCheckbox.setChecked(true);
        updateCheckboxes();
        
        // need to copy it so we can mutate it
        tableSorts = new ArrayList<SortSpec>(Arrays.asList(TRIAGE_SORT_SPECS));
    }
    
    public void setupPassRate() {
        // easier if we ensure it's deselected and then select it
        selectColumns(PASS_RATE_GROUP_COLUMNS);
        statusGroupCheckbox.setChecked(true);
        groupCheckbox.setChecked(false);
        updateCheckboxes();
        
        // need to copy it so we can mutate it
        tableSorts = new ArrayList<SortSpec>(Arrays.asList(PASS_RATE_SORT_SPECS));
    }

    private void createTable() {
        int numColumns = fields.size();
        String[][] columns = new String[numColumns][2];
        for (int i = 0; i < numColumns; i++) {
            String field = fields.get(i);
            columns[i][0] = field;
            columns[i][1] = fieldNames.get(field);
        }
        
        RpcDataSource dataSource = testDataSource;
        if (isAnyGroupingEnabled()) {
            if (isTestGroupingEnabled) {
                groupDataSource = TestGroupDataSource.getTestGroupDataSource();
            } else {
                groupDataSource = TestGroupDataSource.getStatusCountDataSource();
            }

            updateGroupColumns();
            dataSource = groupDataSource;
        } else {
            dataSource = testDataSource;
        }
        
        table = new DynamicTable(columns, dataSource);
        table.addFilter(sqlConditionFilter);
        table.setRowsPerPage(ROWS_PER_PAGE);
        table.makeClientSortable();
        table.setClickable(true);
        table.sinkRightClickEvents();
        table.addListener(this);
        table.setWidgetFactory(this);
        restoreTableSorting();
        
        tableDecorator = new TableDecorator(table);
        tableDecorator.addPaginators();
        Panel tablePanel = RootPanel.get("table_table");
        tablePanel.clear();
        tablePanel.add(tableDecorator);
        
        selectionManager = new SelectionManager(table, false);
        selectionManager.addListener(this);
    }

    private void saveOptions(boolean doSaveCondition) {
        if (doSaveCondition) {
            commonPanel.saveSqlCondition();
        }
        
        fields.clear();
        for (Item item : columnSelect.getSelectedItems()) {
            fields.add(item.value);
        }
        
        isTestGroupingEnabled = groupCheckbox.isChecked();
        isStatusCountEnabled = statusGroupCheckbox.isChecked();
    }

    private void updateGroupColumns() {
        List<String> groupFields = new ArrayList<String>();
        for (String field : fields) {
            if (!field.equals(TestGroupDataSource.GROUP_COUNT_FIELD) &&
                !field.equals(DataTable.WIDGET_COLUMN)) {
                groupFields.add(field);
            }
        }
        groupDataSource.setGroupColumns(groupFields.toArray(new String[0]));
    }
    
    private void saveTableSorting() {
        if (table != null) {
            // we need our own copy so we can modify it later
            tableSorts = new ArrayList<SortSpec>(table.getSortSpecs());
        }
    }

    private void restoreTableSorting() {
        // remove sorts on columns that we no longer have
        for (Iterator<SortSpec> i = tableSorts.iterator(); i.hasNext();) {
            if (!fields.contains(i.next().getField())) {
                i.remove();
            }
        }
        if (tableSorts.isEmpty()) {
            // default to sorting on the first column
            SortSpec sortSpec = new SortSpec(fields.get(0), SortDirection.ASCENDING);
            tableSorts = Arrays.asList(new SortSpec[] {sortSpec});
        }
        
        for (ListIterator<SortSpec> i = tableSorts.listIterator(tableSorts.size()); 
             i.hasPrevious();) {
            SortSpec sortSpec = i.previous();
            table.sortOnColumn(sortSpec.getField(), sortSpec.getDirection());
        }
    }

    @Override
    public void refresh() {
        createTable();
        JSONObject condition = commonPanel.getSavedConditionArgs();
        sqlConditionFilter.setAllParameters(condition);
        table.refresh();
    }

    public void doQuery() {
        if (columnSelect.getSelectedItemCount() == 0) {
            NotifyManager.getInstance().showError("You must select columns");
            return;
        }
        saveOptions(true);
        refresh();
    }

    public void onRowClicked(int rowIndex, JSONObject row) {
        Event event = Event.getCurrentEvent();
        TestSet testSet = getTestSet(row);
        if (RightClickTable.isRightClick(event)) {
            if (selectionManager.getSelectedObjects().size() > 0) {
                testSet = getTestSet(selectionManager.getSelectedObjects());
            }
            ContextMenu menu = getContextMenu(testSet);
            menu.showAtWindow(event.getClientX(), event.getClientY());
            return;
        }
        
        if (isSelectEvent(event)) {
            selectionManager.toggleSelected(row);
            return;
        }
        
        if (isAnyGroupingEnabled()) {
            doDrilldown(testSet);
        } else {
            TkoUtils.getTestId(testSet, listener);
        }
    }

    private ContextMenu getContextMenu(final TestSet testSet) {
        TestContextMenu menu = new TestContextMenu(testSet, listener);
        
        if (!menu.addViewDetailsIfSingleTest() && isAnyGroupingEnabled()) {
            menu.addItem("Drill down", new Command() {
                public void execute() {
                    doDrilldown(testSet);
                }
            });
        }
        
        menu.addLabelItems();
        return menu;
    }

    private void doDrilldown(TestSet testSet) {
        commonPanel.setCondition(testSet);
        uncheckBothCheckboxes();
        updateCheckboxes();
        selectColumns(DEFAULT_COLUMNS);
        doQuery();
        updateHistory();
    }

    private void uncheckBothCheckboxes() {
        groupCheckbox.setChecked(false);
        statusGroupCheckbox.setChecked(false);
    }

    private TestSet getTestSet(JSONObject row) {
        ConditionTestSet testSet;
        if (isAnyGroupingEnabled()) {
            testSet = new ConditionTestSet(false, commonPanel.getSavedConditionArgs());
            for (String field : fields) {
                if (field.equals(TestGroupDataSource.GROUP_COUNT_FIELD) ||
                    field.equals(DataTable.WIDGET_COLUMN)) {
                    continue;
                }
                testSet.setField(field, Utils.jsonToString(row.get(field)));
            }
        } else {
            testSet = new ConditionTestSet(true);
            testSet.setField("test_idx", 
                             Utils.jsonToString(row.get("test_idx")));
        }
        return testSet;
    }
    
    private TestSet getTestSet(Collection<JSONObject> selectedObjects) {
        CompositeTestSet compositeSet = new CompositeTestSet();
        for (JSONObject row : selectedObjects) {
            compositeSet.add(getTestSet(row));
        }
        return compositeSet;
    }

    public void onTableRefreshed() {
        selectionManager.refreshSelection();
        
        saveTableSorting();
        updateHistory();
    }

    private void updateCheckboxes() {
        ensureItemRemoved(COUNT_NAME);
        ensureItemRemoved(STATUS_COUNTS_NAME);
        groupCheckbox.setEnabled(true);
        statusGroupCheckbox.setEnabled(true);
        
        if (groupCheckbox.isChecked()) {
            columnSelect.addReadonlySelectedItem(COUNT_NAME, TestGroupDataSource.GROUP_COUNT_FIELD);
            statusGroupCheckbox.setEnabled(false);
        } else if (statusGroupCheckbox.isChecked()) {
            columnSelect.addReadonlySelectedItem(STATUS_COUNTS_NAME, DataTable.WIDGET_COLUMN);
            groupCheckbox.setEnabled(false);
        }
    }

    private void ensureItemRemoved(String itemName) {
        try {
            columnSelect.removeItem(itemName);
        } catch (IllegalArgumentException exc) {}
    }

    public ContextMenu getActionMenu() {
        TestSet tests;
        if (selectionManager.isEmpty()) {
            tests = getWholeTableSet();
        } else {
            tests = getTestSet(selectionManager.getSelectedObjects());
        }
        return getContextMenu(tests);
    }

    private ConditionTestSet getWholeTableSet() {
        return new ConditionTestSet(false, commonPanel.getSavedConditionArgs());
    }

    public void onSelectAll(boolean visibleOnly) {
        if (visibleOnly) {
            selectionManager.selectVisible();
        } else {
            selectionManager.selectAll();
        }
    }

    public void onSelectNone() {
        selectionManager.deselectAll();
    }

    @Override
    protected Map<String, String> getHistoryArguments() {
        Map<String, String> arguments = super.getHistoryArguments();
        if (table != null) {
            arguments.put("columns", Utils.joinStrings(",", fields));
            arguments.put("sort", Utils.joinStrings(",", tableSorts));
            commonPanel.addHistoryArguments(arguments);
        }
        return arguments;
    }

    @Override
    public void handleHistoryArguments(Map<String, String> arguments) {
        super.handleHistoryArguments(arguments);
        
        handleSortString(arguments.get("sort"));
        
        columnSelect.deselectAll();
        uncheckBothCheckboxes();
        String[] columns = arguments.get("columns").split(",");
        for (String column : columns) {
            if (column.equals(TestGroupDataSource.GROUP_COUNT_FIELD)) {
                groupCheckbox.setChecked(true);
            } else if (column.equals(DataTable.WIDGET_COLUMN)) {
                statusGroupCheckbox.setChecked(true);
            } else {
                columnSelect.selectItemByValue(column);
            }
        }
        updateCheckboxes();
        saveOptions(true);
    }

    @Override
    protected void fillDefaultHistoryValues(Map<String, String> arguments) {
        Utils.setDefaultValue(arguments, "sort", DEFAULT_COLUMNS[0]);
        Utils.setDefaultValue(arguments, "columns", 
                        Utils.joinStrings(",", Arrays.asList(DEFAULT_COLUMNS)));
        
    }

    private void handleSortString(String sortString) {
        tableSorts.clear();
        String[] components = sortString.split(",");
        for (String component : components) {
            tableSorts.add(SortSpec.fromString(component));
        }
    }

    public void onAdd(Collection<JSONObject> objects) {
        selectionManager.refreshSelection();
    }

    public void onRemove(Collection<JSONObject> objects) {
        selectionManager.refreshSelection();
    }

    public void onClick(Widget sender) {
        if (sender == queryButton) {
            doQuery();
            updateHistory();
        } else if (sender == groupCheckbox || sender == statusGroupCheckbox) {
            updateCheckboxes();
        }
    }

    private boolean isAnyGroupingEnabled() {
        return isTestGroupingEnabled || isStatusCountEnabled;
    }

    public Widget createWidget(int row, int cell, JSONObject rowObject) {
        assert isStatusCountEnabled;
        StatusSummary statusSummary = StatusSummary.getStatusSummary(rowObject);
        SimplePanel panel = new SimplePanel();
        panel.add(new HTML(statusSummary.formatStatusCounts()));
        panel.getElement().getStyle().setProperty("backgroundColor", 
                                                  statusSummary.getColor());
        return panel;
    }

    @Override
    protected boolean hasFirstQueryOccurred() {
        return table != null;
    }

    public void onSetControlsVisible(boolean visible) {
        TkoUtils.setElementVisible("table_all_controls", visible);
    }
}
