package autotest.tko;

import autotest.common.Utils;
import autotest.common.CustomHistory.HistoryToken;
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
import autotest.common.ui.MultiListSelectPresenter;
import autotest.common.ui.NotifyManager;
import autotest.common.ui.RightClickTable;
import autotest.common.ui.MultiListSelectPresenter.Item;
import autotest.common.ui.TableActionsPanel.TableActionsWithExportCsvListener;
import autotest.tko.CommonPanel.CommonPanelListener;

import com.google.gwt.event.dom.client.ClickEvent;
import com.google.gwt.event.dom.client.ClickHandler;
import com.google.gwt.json.client.JSONArray;
import com.google.gwt.json.client.JSONObject;
import com.google.gwt.user.client.Command;
import com.google.gwt.user.client.Event;
import com.google.gwt.user.client.History;
import com.google.gwt.user.client.ui.Button;
import com.google.gwt.user.client.ui.CheckBox;
import com.google.gwt.user.client.ui.HTML;
import com.google.gwt.user.client.ui.Panel;
import com.google.gwt.user.client.ui.SimplePanel;
import com.google.gwt.user.client.ui.VerticalPanel;
import com.google.gwt.user.client.ui.Widget;

import java.util.ArrayList;
import java.util.Arrays;
import java.util.Collection;
import java.util.Iterator;
import java.util.List;
import java.util.ListIterator;
import java.util.Map;
import java.util.Set;

// TODO: consolidate logic between this and HeaderSelect
public class TableView extends ConditionTabView 
                       implements DynamicTableListener, TableActionsWithExportCsvListener, 
                                  ClickHandler, TableWidgetFactory, CommonPanelListener, 
                                  MultiListSelectPresenter.GeneratorHandler {
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

    private static enum GroupingType {NO_GROUPING, TEST_GROUPING, STATUS_COUNTS}

    /**
     * HeaderField representing a grouped count of some kind.
     */
    private static class GroupCountField extends HeaderField {
        public GroupCountField(String name, String sqlName) {
            super(name, sqlName);
        }

        @Override
        public Item getItem() {
            return Item.createGeneratedItem(getName(), getSqlName());
        }

        @Override
        public String getSqlCondition(String value) {
            throw new UnsupportedOperationException();
        }
    }

    private TestSelectionListener listener;
    
    private DynamicTable table;
    private TableDecorator tableDecorator;
    private SelectionManager selectionManager;
    private SimpleFilter sqlConditionFilter = new SimpleFilter();
    private RpcDataSource testDataSource = new TestViewDataSource();
    private RpcDataSource iterationDataSource = new IterationDataSource();
    private TestGroupDataSource groupDataSource = TestGroupDataSource.getTestGroupDataSource();
    private RpcDataSource currentDataSource;

    private HeaderFieldCollection headerFields = new HeaderFieldCollection();
    private MultiListSelectPresenter columnSelect = new MultiListSelectPresenter();
    private ParameterizedFieldListPresenter parameterizedFieldPresenter =
        new ParameterizedFieldListPresenter(headerFields);

    private DoubleListSelector columnSelectDisplay = new DoubleListSelector();
    private ParameterizedFieldListDisplay parameterizedFieldDisplay =
        new ParameterizedFieldListDisplay();
    private CheckBox groupCheckbox = new CheckBox("Group by these columns and show counts");
    private CheckBox statusGroupCheckbox = 
        new CheckBox("Group by these columns and show pass rates");
    private Button queryButton = new Button("Query");
    private Panel tablePanel = new SimplePanel();

    private HeaderFieldCollection savedColumns = new HeaderFieldCollection();
    private List<SortSpec> tableSorts = new ArrayList<SortSpec>();
    private Item iterationGenerator = 
        ParameterizedField.getGenerator(IterationResultField.BASE_NAME);

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
        super.initialize();

        columnSelect.setGeneratorHandler(this);
        columnSelect.bindDisplay(columnSelectDisplay);

        headerFields.populateFromList("all_fields");
        parameterizedFieldPresenter.bindDisplay(parameterizedFieldDisplay);

        for (HeaderField field : headerFields) {
            columnSelect.addItem(field.getItem());
        }
        columnSelect.addItem(iterationGenerator);

        headerFields.add(new GroupCountField(COUNT_NAME, TestGroupDataSource.GROUP_COUNT_FIELD));
        headerFields.add(new GroupCountField(STATUS_COUNTS_NAME, DataTable.WIDGET_COLUMN));

        selectColumnsByName(DEFAULT_COLUMNS);
        updateViewFromState();

        queryButton.addClickHandler(this);
        groupCheckbox.addClickHandler(this);
        statusGroupCheckbox.addClickHandler(this);
        
        Panel columnPanel = new VerticalPanel();
        columnPanel.add(columnSelectDisplay);
        columnPanel.add(parameterizedFieldDisplay);
        columnPanel.add(groupCheckbox);
        columnPanel.add(statusGroupCheckbox);
        
        addWidget(columnPanel, "table_column_select");
        addWidget(queryButton, "table_query_controls");
        addWidget(tablePanel, "table_table");
    }
    
    private void selectColumnsByName(String[] columnNames) {
        savedColumns.clear();
        for (String name : columnNames) {
            savedColumns.add(headerFields.getFieldByName(name));
        }
        cleanupSortsForNewColumns();
    }
    
    public void setupDefaultView() {
        tableSorts.clear();
        selectColumnsByName(DEFAULT_COLUMNS);
        updateViewFromState();
    }

    public void setupJobTriage() {
        selectColumnsByName(TRIAGE_GROUP_COLUMNS);
        // need to copy it so we can mutate it
        tableSorts = new ArrayList<SortSpec>(Arrays.asList(TRIAGE_SORT_SPECS));
        updateViewFromState();
    }

    public void setupPassRate() {
        tableSorts.clear();
        selectColumnsByName(PASS_RATE_GROUP_COLUMNS);
        updateViewFromState();
    }

    private void createTable() {
        String[][] columns = buildColumnSpecs();
        currentDataSource = getDataSource();

        table = new DynamicTable(columns, currentDataSource);
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
        tableDecorator.addTableActionsWithExportCsvListener(this);
        tablePanel.clear();
        tablePanel.add(tableDecorator);
        
        selectionManager = new SelectionManager(table, false);
    }

    private String[][] buildColumnSpecs() {
        int numColumns = savedColumns.size();
        String[][] columns = new String[numColumns][2];
        int i = 0;
        for (HeaderField field : savedColumns) {
            columns[i][0] = field.getAttributeName();
            columns[i][1] = field.getName();
            i++;
        }
        return columns;
    }

    private RpcDataSource getDataSource() {
        GroupingType groupingType = getActiveGrouping();
        if (groupingType == GroupingType.NO_GROUPING) {
            if (isIterationFieldPresentIn(savedColumns)) {
                return iterationDataSource;
            }
            return testDataSource;
        } else if (groupingType == GroupingType.TEST_GROUPING) {
            groupDataSource = TestGroupDataSource.getTestGroupDataSource();
        } else {
            groupDataSource = TestGroupDataSource.getStatusCountDataSource();
        }
        
        updateGroupColumns();
        return groupDataSource;
    }

    private boolean isIterationFieldPresentIn(Collection<HeaderField> fields) {
        for (HeaderField field : fields) {
            if (field.getName().startsWith(IterationResultField.BASE_NAME)) {
                return true;
            }
        }
        return false;
    }

    private void updateStateFromView() {
        commonPanel.updateStateFromView();
        parameterizedFieldPresenter.updateStateFromView();
        savedColumns.clear();
        for (Item item : columnSelect.getSelectedItems()) {
            savedColumns.add(headerFields.getFieldByName(item.name));
        }
    }
    
    private void updateViewFromState() {
        commonPanel.updateViewFromState();
        selectColumnsInView();
        parameterizedFieldPresenter.updateViewFromState();
    }

    private void selectColumnsInView() {
        List<String> fieldNames = new ArrayList<String>();
        for (HeaderField field : savedColumns) {
            Item item = field.getItem();
            if (item.isGeneratedItem) {
                columnSelect.addItem(item);
            }
            fieldNames.add(field.getName());
        }
        columnSelect.setSelectedItemsByName(fieldNames);
        updateCheckboxesFromFields();
    }

    private void updateGroupColumns() {
        List<String> groupFields = new ArrayList<String>();
        for (HeaderField field : savedColumns) {
            if (!isGroupField(field)) {
                groupFields.add(field.getAttributeName());
            }
        }

        groupDataSource.setGroupColumns(groupFields.toArray(new String[0]));
    }

    private boolean isGroupField(HeaderField field) {
        return field instanceof GroupCountField;
    }
    
    private void saveTableSorting() {
        if (table != null) {
            // we need our own copy so we can modify it later
            tableSorts = new ArrayList<SortSpec>(table.getSortSpecs());
        }
    }

    private void restoreTableSorting() {
        for (ListIterator<SortSpec> i = tableSorts.listIterator(tableSorts.size()); 
             i.hasPrevious();) {
            SortSpec sortSpec = i.previous();
            table.sortOnColumn(sortSpec.getField(), sortSpec.getDirection());
        }
    }

    private void cleanupSortsForNewColumns() {
        // remove sorts on columns that we no longer have
        for (Iterator<SortSpec> i = tableSorts.iterator(); i.hasNext();) {
            String attribute = i.next().getField();
            if (!isAttributeSelected(attribute)) {
                i.remove();
            }
        }

        if (tableSorts.isEmpty()) {
            // default to sorting on the first column
            HeaderField field = savedColumns.iterator().next();
            SortSpec sortSpec = new SortSpec(field.getAttributeName(), SortDirection.ASCENDING);
            tableSorts = new ArrayList<SortSpec>();
            tableSorts.add(sortSpec);
        }
    }

    private boolean isAttributeSelected(String attribute) {
        for (HeaderField field : savedColumns) {
            if (field.getAttributeName().equals(attribute)) {
                return true;
            }
        }
        return false;
    }

    @Override
    public void refresh() {
        createTable();
        JSONObject condition = commonPanel.getConditionArgs();
        for (HeaderField field : headerFields) {
            field.addQueryParameters(condition);
        }
        sqlConditionFilter.setAllParameters(condition);
        table.refresh();
    }

    public void doQuery() {
        if (columnSelect.getSelectedItems().isEmpty()) {
            NotifyManager.getInstance().showError("You must select columns");
            return;
        }
        if (!parameterizedFieldPresenter.areAllInputsFilled()) {
            NotifyManager.getInstance().showError(
                    "You must enter attributes for all iteration fields");
            return;
        }
        updateStateFromView();
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

        HistoryToken historyToken;
        if (isAnyGroupingEnabled()) {
            historyToken = getDrilldownHistoryToken(testSet);
        } else {
            historyToken = listener.getSelectTestHistoryToken(testSet.getTestIndex());
        }
        openHistoryToken(historyToken);
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

    private HistoryToken getDrilldownHistoryToken(TestSet testSet) {
        saveHistoryState();
        commonPanel.refineCondition(testSet);
        selectColumnsByName(DEFAULT_COLUMNS);
        HistoryToken historyToken = getHistoryArguments();
        restoreHistoryState();
        return historyToken;
    }
    
    private void doDrilldown(TestSet testSet) {
        History.newItem(getDrilldownHistoryToken(testSet).toString());
    }

    private TestSet getTestSet(JSONObject row) {
        if (!isAnyGroupingEnabled()) {
            return new SingleTestSet((int) row.get("test_idx").isNumber().doubleValue());
        }

        ConditionTestSet testSet = new ConditionTestSet(commonPanel.getConditionArgs());
        for (HeaderField field : savedColumns) {
            if (isGroupField(field)) {
                continue;
            }

            String value = Utils.jsonToString(row.get(field.getAttributeName()));
            testSet.addCondition(field.getSqlCondition(value));
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
        assert !(groupCheckbox.getValue() && statusGroupCheckbox.getValue());

        // grouping is not currently supported with iteration results
        if (isIterationFieldPresentIn(headerFields)) {
            groupCheckbox.setEnabled(false);
            statusGroupCheckbox.setEnabled(false);
            return;
        }

        groupCheckbox.setEnabled(true);
        statusGroupCheckbox.setEnabled(true);
        if (groupCheckbox.getValue()) {
            statusGroupCheckbox.setEnabled(false);
        } else if (statusGroupCheckbox.getValue()) {
            groupCheckbox.setEnabled(false);
        }
    }

    private void updateFieldsFromCheckboxes() {
        ensureItemRemoved(COUNT_NAME);
        ensureItemRemoved(STATUS_COUNTS_NAME);

        if (groupCheckbox.getValue()) {
            addSpecialItem(COUNT_NAME);
        } else if (statusGroupCheckbox.getValue()) {
            addSpecialItem(STATUS_COUNTS_NAME);
        }
    }

    private void updateCheckboxesFromFields() {
        groupCheckbox.setValue(false);
        statusGroupCheckbox.setValue(false);

        Set<String> selectedNames = 
            MultiListSelectPresenter.getItemNameSet(columnSelect.getSelectedItems());
        if (selectedNames.contains(COUNT_NAME)) {
            groupCheckbox.setValue(true);
        } 
        if (selectedNames.contains(STATUS_COUNTS_NAME)) {
            statusGroupCheckbox.setValue(true);
        }

        setCheckboxesEnabled();
        updateIterationGenerator();
    }
    
    private void updateIterationGenerator() {
        ensureItemRemoved(iterationGenerator.name);
        if (!groupCheckbox.getValue() && !statusGroupCheckbox.getValue()) {
            columnSelect.addItem(iterationGenerator);
        }
    }

    private void addSpecialItem(String itemName) {
        HeaderField field = headerFields.getFieldByName(itemName);
        assert isGroupField(field);
        columnSelect.addItem(field.getItem());
    }

    private void ensureItemRemoved(String itemName) {
        try {
            columnSelect.removeItemByName(itemName);
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
        return new ConditionTestSet(commonPanel.getConditionArgs());
    }

    @Override
    public HistoryToken getHistoryArguments() {
        HistoryToken arguments = super.getHistoryArguments();
        if (table != null) {
            arguments.put("columns", Utils.joinStrings(",", getSavedColumnNames()));
            arguments.put("sort", Utils.joinStrings(",", tableSorts));
            commonPanel.addHistoryArguments(arguments);
        }
        headerFields.addHistoryArguments(arguments);
        return arguments;
    }

    private List<String> getSavedColumnNames() {
        List<String> names = new ArrayList<String>();
        for (HeaderField field : savedColumns) {
            names.add(field.getName());
        }
        return names;
    }

    @Override
    public void handleHistoryArguments(Map<String, String> arguments) {
        super.handleHistoryArguments(arguments);
        String[] columns = arguments.get("columns").split(",");
        addParameterizedFields(columns);
        selectColumnsByName(columns);
        savedColumns.handleHistoryArguments(arguments);
        handleSortString(arguments.get("sort"));
        updateViewFromState();
    }

    private void addParameterizedFields(String[] columns) {
        for (String name : columns) {
            if (!headerFields.containsName(name)) {
                ParameterizedField field = ParameterizedField.fromName(name);
                parameterizedFieldPresenter.addField(field);
            }
        }
    }

    @Override
    protected void fillDefaultHistoryValues(Map<String, String> arguments) {
        HeaderField defaultSortField = headerFields.getFieldByName(DEFAULT_COLUMNS[0]);
        Utils.setDefaultValue(arguments, "sort", defaultSortField.getSqlName());
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

    public void onClick(ClickEvent event) {
        if (event.getSource() == queryButton) {
            doQuery();
            updateHistory();
        } else if (event.getSource() == groupCheckbox || event.getSource() == statusGroupCheckbox) {
            updateFieldsFromCheckboxes();
            setCheckboxesEnabled();
            updateIterationGenerator();
        }
    }

    @Override
    public Item generateItem(Item generatorItem) {
        Item item = parameterizedFieldPresenter.generateItem(generatorItem);
        updateCheckboxesFromFields();
        return item;
    }

    @Override
    public void onRemoveGeneratedItem(Item generatedItem) {
        HeaderField field = headerFields.getFieldByName(generatedItem.name);
        if (!isGroupField(field)) {
            parameterizedFieldPresenter.onRemoveGeneratedItem(generatedItem);
        }
        updateCheckboxesFromFields();
    }

    private boolean isAnyGroupingEnabled() {
        return getActiveGrouping() != GroupingType.NO_GROUPING;
    }
    
    private GroupingType getActiveGrouping() {
        for (HeaderField field : savedColumns) {
            if (field.getName().equals(COUNT_NAME)) {
                return GroupingType.TEST_GROUPING;
            }
            if (field.getName().equals(STATUS_COUNTS_NAME)) {
                return GroupingType.STATUS_COUNTS;
            }
        }
        return GroupingType.NO_GROUPING;
    }

    public Widget createWidget(int row, int cell, JSONObject rowObject) {
        assert getActiveGrouping() == GroupingType.STATUS_COUNTS;
        StatusSummary statusSummary = StatusSummary.getStatusSummary(rowObject);
        SimplePanel panel = new SimplePanel();
        panel.add(new HTML(statusSummary.formatContents()));
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

    public void onExportCsv() {
        JSONObject extraParams = new JSONObject();
        extraParams.put("columns", buildCsvColumnSpecs());
        TkoUtils.doCsvRequest(currentDataSource, extraParams);
    }
    
    private JSONArray buildCsvColumnSpecs() {
        String[][] columnSpecs = buildColumnSpecs();
        JSONArray jsonColumnSpecs = new JSONArray();
        for (String[] columnSpec : columnSpecs) {
            JSONArray jsonColumnSpec = Utils.stringsToJSON(Arrays.asList(columnSpec));
            jsonColumnSpecs.set(jsonColumnSpecs.size(), jsonColumnSpec);
        }
        return jsonColumnSpecs;
    }
}
