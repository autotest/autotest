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
import autotest.common.ui.ContextMenu;
import autotest.common.ui.DoubleListSelector;
import autotest.common.ui.NotifyManager;
import autotest.common.ui.RightClickTable;
import autotest.common.ui.DoubleListSelector.Item;
import autotest.common.ui.TableActionsPanel.TableActionsListener;
import autotest.tko.CommonPanel.CommonPanelListener;
import autotest.tko.TkoUtils.FieldInfo;

import com.google.gwt.json.client.JSONObject;
import com.google.gwt.user.client.Command;
import com.google.gwt.user.client.Event;
import com.google.gwt.user.client.ui.Button;
import com.google.gwt.user.client.ui.ChangeListener;
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

// TODO(showard): make TableView use HeaderFields
public class TableView extends ConditionTabView 
                       implements DynamicTableListener, TableActionsListener, ClickListener,
                                  TableWidgetFactory, CommonPanelListener, ChangeListener {
    private static final int ROWS_PER_PAGE = 30;
    private static final String COUNT_NAME = "Count in group";
    private static final String STATUS_COUNTS_NAME = "Test pass rate";
    private static final String[] DEFAULT_COLUMNS = 
        {"Test index", "Test name", "Job tag", "Hostname", "Status"};
    private static final String[] TRIAGE_GROUP_COLUMNS =
        {"Test name", "Status", COUNT_NAME, "Reason"};
    private static final String[] PASS_RATE_GROUP_COLUMNS =
        {"Hostname", STATUS_COUNTS_NAME};
    private static final SortSpec[] TRIAGE_SORT_SPECS = {
        new SortSpec("test_name", SortDirection.ASCENDING),
        new SortSpec("status", SortDirection.ASCENDING),
        new SortSpec("reason", SortDirection.ASCENDING),
    };

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
    private Button queryButton = new Button("Query");
    
    private boolean isTestGroupingEnabled = false, isStatusCountEnabled = false;
    private List<String> columnNames = new ArrayList<String>();
    private List<SortSpec> tableSorts = new ArrayList<SortSpec>();
    private Map<String, String> namesToFields = new HashMap<String, String>();
    private Map<String, String> fieldsToNames = new HashMap<String, String>();
    
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
            namesToFields.put(fieldInfo.name, fieldInfo.field);
            fieldsToNames.put(fieldInfo.field, fieldInfo.name);
            columnSelect.addItem(fieldInfo.name, fieldInfo.field);
        }
        namesToFields.put(COUNT_NAME, TestGroupDataSource.GROUP_COUNT_FIELD);
        namesToFields.put(STATUS_COUNTS_NAME, DataTable.WIDGET_COLUMN);
        
        selectColumns(DEFAULT_COLUMNS);
        saveOptions(false);
        
        columnSelect.setListener(this);
        queryButton.addClickListener(this);
        groupCheckbox.addClickListener(this);
        statusGroupCheckbox.addClickListener(this);
        
        Panel columnPanel = new VerticalPanel();
        columnPanel.add(columnSelect);
        columnPanel.add(groupCheckbox);
        columnPanel.add(statusGroupCheckbox);
        
        RootPanel.get("table_column_select").add(columnPanel);
        RootPanel.get("table_query_controls").add(queryButton);
    }

    private void selectColumns(String[] columnNames) {
        columnSelect.deselectAll();
        for(String columnName : columnNames) {
            if (columnName.equals(COUNT_NAME)) {
                addSpecialItem(COUNT_NAME);
            } else if (columnName.equals(STATUS_COUNTS_NAME)) {
                addSpecialItem(STATUS_COUNTS_NAME);
            } else {
                columnSelect.selectItem(columnName);
            }
        }
        updateCheckboxesFromFields();
    }
    
    public void setupDefaultView() {
        selectColumns(DEFAULT_COLUMNS);
        tableSorts.clear();
    }

    public void setupJobTriage() {
        selectColumns(TRIAGE_GROUP_COLUMNS);
        // need to copy it so we can mutate it
        tableSorts = new ArrayList<SortSpec>(Arrays.asList(TRIAGE_SORT_SPECS));
    }

    public void setupPassRate() {
        selectColumns(PASS_RATE_GROUP_COLUMNS);
    }

    private void createTable() {
        int numColumns = columnNames.size();
        String[][] columns = new String[numColumns][2];
        for (int i = 0; i < numColumns; i++) {
            String columnName = columnNames.get(i);
            columns[i][0] = namesToFields.get(columnName);
            columns[i][1] = columnName;
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
        selectionManager = tableDecorator.addSelectionManager(false);
        tableDecorator.addTableActionsPanel(this, true);
        Panel tablePanel = RootPanel.get("table_table");
        tablePanel.clear();
        tablePanel.add(tableDecorator);
        
        selectionManager = new SelectionManager(table, false);
    }

    private void saveOptions(boolean doSaveCondition) {
        if (doSaveCondition) {
            commonPanel.saveSqlCondition();
        }
        
        columnNames.clear();
        for (Item item : columnSelect.getSelectedItems()) {
            columnNames.add(item.name);
        }
        
        isTestGroupingEnabled = groupCheckbox.isChecked();
        isStatusCountEnabled = statusGroupCheckbox.isChecked();
    }

    private void updateGroupColumns() {
        List<String> groupFields = new ArrayList<String>();
        for (String columnName : columnNames) {
            if (!isSpecialColumnName(columnName)) {
                groupFields.add(namesToFields.get(columnName));
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
            String columnName = fieldsToNames.get(i.next().getField());
            if (!columnNames.contains(columnName)) {
                i.remove();
            }
        }
        if (tableSorts.isEmpty()) {
            // default to sorting on the first column
            SortSpec sortSpec = new SortSpec(namesToFields.get(columnNames.get(0)), 
                                             SortDirection.ASCENDING);
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
            listener.onSelectTest(testSet.getTestIndex());
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
        commonPanel.refineCondition(testSet);
        selectColumns(DEFAULT_COLUMNS);
        doQuery();
        updateHistory();
    }

    private TestSet getTestSet(JSONObject row) {
        if (!isAnyGroupingEnabled()) {
            return new SingleTestSet((int) row.get("test_idx").isNumber().doubleValue());
        }

        ConditionTestSet testSet = new ConditionTestSet(commonPanel.getSavedConditionArgs());
        for (String columnName : columnNames) {
            if (isSpecialColumnName(columnName)) {
                continue;
            }

            String field = namesToFields.get(columnName);
            testSet.setField(field, Utils.jsonToString(row.get(field)));
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
    
    private void setCheckboxesEnabled() {
        assert !(groupCheckbox.isChecked() && statusGroupCheckbox.isChecked());
        groupCheckbox.setEnabled(true);
        statusGroupCheckbox.setEnabled(true);
        if (groupCheckbox.isChecked()) {
            statusGroupCheckbox.setEnabled(false);
        } else if (statusGroupCheckbox.isChecked()) {
            groupCheckbox.setEnabled(false);
        }
    }

    private void updateFieldsFromCheckboxes() {
        ensureItemRemoved(COUNT_NAME);
        ensureItemRemoved(STATUS_COUNTS_NAME);
        
        if (groupCheckbox.isChecked()) {
            addSpecialItem(COUNT_NAME);
        } else if (statusGroupCheckbox.isChecked()) {
            addSpecialItem(STATUS_COUNTS_NAME);
        }
        
        setCheckboxesEnabled();
    }
    
    private void updateCheckboxesFromFields() {
        groupCheckbox.setChecked(false);
        statusGroupCheckbox.setChecked(false);
        
        if (columnSelect.isItemSelected(COUNT_NAME)) {
            groupCheckbox.setChecked(true);
        } 
        if (columnSelect.isItemSelected(STATUS_COUNTS_NAME)) {
            statusGroupCheckbox.setChecked(true);
        }
        
        setCheckboxesEnabled();
    }
    
    private void addSpecialItem(String itemName) {
        assert isSpecialColumnName(itemName);
        String fieldName;
        if (itemName.equals(COUNT_NAME)) {
            fieldName = TestGroupDataSource.GROUP_COUNT_FIELD;
        } else { // STATUS_COUNT_NAME
            fieldName = DataTable.WIDGET_COLUMN;
        }
        columnSelect.addItem(itemName, fieldName);
        columnSelect.selectItem(itemName);
    }
    
    private boolean isSpecialColumnName(String columnName) {
        return columnName.equals(COUNT_NAME) || columnName.equals(STATUS_COUNTS_NAME);
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
        return new ConditionTestSet(commonPanel.getSavedConditionArgs());
    }

    @Override
    protected Map<String, String> getHistoryArguments() {
        Map<String, String> arguments = super.getHistoryArguments();
        if (table != null) {
            arguments.put("columns", Utils.joinStrings(",", columnNames));
            arguments.put("sort", Utils.joinStrings(",", tableSorts));
            commonPanel.addHistoryArguments(arguments);
        }
        return arguments;
    }

    @Override
    public void handleHistoryArguments(Map<String, String> arguments) {
        super.handleHistoryArguments(arguments);
        
        handleSortString(arguments.get("sort"));
        
        String[] columns = arguments.get("columns").split(",");
        selectColumns(columns);
        saveOptions(true);
    }

    @Override
    protected void fillDefaultHistoryValues(Map<String, String> arguments) {
        Utils.setDefaultValue(arguments, "sort", namesToFields.get(DEFAULT_COLUMNS[0]));
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

    public void onClick(Widget sender) {
        if (sender == queryButton) {
            doQuery();
            updateHistory();
        } else if (sender == groupCheckbox || sender == statusGroupCheckbox) {
            updateFieldsFromCheckboxes();
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

    public void onChange(Widget sender) {
        assert sender == columnSelect;
        updateCheckboxesFromFields();
    }
}
