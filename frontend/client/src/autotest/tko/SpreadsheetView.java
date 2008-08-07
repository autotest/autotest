package autotest.tko;

import autotest.common.JsonRpcCallback;
import autotest.common.JsonRpcProxy;
import autotest.common.UnmodifiableSublistView;
import autotest.common.Utils;
import autotest.common.ui.ContextMenu;
import autotest.common.ui.NotifyManager;
import autotest.common.ui.RightClickTable;
import autotest.common.ui.SimpleHyperlink;
import autotest.common.ui.TableActionsPanel;
import autotest.common.ui.DoubleListSelector.Item;
import autotest.common.ui.TableActionsPanel.TableActionsListener;
import autotest.tko.Spreadsheet.CellInfo;
import autotest.tko.Spreadsheet.Header;
import autotest.tko.Spreadsheet.HeaderImpl;
import autotest.tko.Spreadsheet.SpreadsheetListener;
import autotest.tko.TkoUtils.FieldInfo;

import com.google.gwt.json.client.JSONArray;
import com.google.gwt.json.client.JSONObject;
import com.google.gwt.json.client.JSONValue;
import com.google.gwt.user.client.Command;
import com.google.gwt.user.client.Event;
import com.google.gwt.user.client.Window;
import com.google.gwt.user.client.WindowResizeListener;
import com.google.gwt.user.client.ui.Button;
import com.google.gwt.user.client.ui.CheckBox;
import com.google.gwt.user.client.ui.ClickListener;
import com.google.gwt.user.client.ui.HTML;
import com.google.gwt.user.client.ui.MenuBar;
import com.google.gwt.user.client.ui.Panel;
import com.google.gwt.user.client.ui.RootPanel;
import com.google.gwt.user.client.ui.VerticalPanel;
import com.google.gwt.user.client.ui.Widget;

import java.util.Arrays;
import java.util.HashMap;
import java.util.List;
import java.util.Map;

public class SpreadsheetView extends ConditionTabView 
                             implements SpreadsheetListener, TableActionsListener {
    public static final String DEFAULT_ROW = "kernel";
    public static final String DEFAULT_COLUMN = "platform";
    
    private static enum DrilldownType {DRILLDOWN_ROW, DRILLDOWN_COLUMN, DRILLDOWN_BOTH}
    
    private static JsonRpcProxy rpcProxy = JsonRpcProxy.getProxy();
    private static JsonRpcProxy afeRpcProxy = JsonRpcProxy.getProxy(JsonRpcProxy.AFE_URL);
    private SpreadsheetViewListener listener;
    protected Header currentRowFields;
    protected Header currentColumnFields;
    protected Map<String,String[]> drilldownMap = new HashMap<String,String[]>();
    
    private HeaderSelect rowSelect = new HeaderSelect();
    private HeaderSelect columnSelect = new HeaderSelect();
    private CheckBox showIncomplete = new CheckBox("Show incomplete tests"); 
    private Button queryButton = new Button("Query");
    private TestGroupDataSource dataSource = TestGroupDataSource.getStatusCountDataSource();
    private Spreadsheet spreadsheet = new Spreadsheet();
    private SpreadsheetDataProcessor spreadsheetProcessor = 
        new SpreadsheetDataProcessor(spreadsheet, dataSource);
    private SpreadsheetSelectionManager selectionManager = 
        new SpreadsheetSelectionManager(spreadsheet, null);
    private TableActionsPanel actionsPanel = new TableActionsPanel(this, false);
    private RootPanel jobCompletionPanel;
    private boolean currentShowIncomplete;
    private boolean notYetQueried = true;
    
    public static interface SpreadsheetViewListener extends TestSelectionListener {
        public void onSwitchToTable(boolean isTriageView);
    }
    
    public SpreadsheetView(SpreadsheetViewListener listener) {
        this.listener = listener;
    }
    
    @Override
    public String getElementId() {
        return "spreadsheet_view";
    }

    @Override
    public void initialize() {
        dataSource.setSkipNumResults(true);
        
        currentRowFields = new HeaderImpl();
        currentRowFields.add(DEFAULT_ROW);
        currentColumnFields = new HeaderImpl();
        currentColumnFields.add(DEFAULT_COLUMN);
        
        for (FieldInfo fieldInfo : TkoUtils.getFieldList("group_fields")) {
            rowSelect.addItem(fieldInfo.name, fieldInfo.field);
            columnSelect.addItem(fieldInfo.name, fieldInfo.field);
        }
        updateWidgets();
        
        queryButton.addClickListener(new ClickListener() {
            public void onClick(Widget sender) {
                doQuery();
                updateHistory();
            } 
        });
        
        spreadsheet.setVisible(false);
        spreadsheet.setListener(this);
        
        SimpleHyperlink swapLink = new SimpleHyperlink("swap");
        swapLink.addClickListener(new ClickListener() {
            public void onClick(Widget sender) {
                Header newRows = getSelectedHeader(columnSelect);
                setSelectedHeader(columnSelect, getSelectedHeader(rowSelect));
                setSelectedHeader(rowSelect, newRows);
            } 
        });
        
        Panel queryControlPanel = new VerticalPanel();
        queryControlPanel.add(showIncomplete);
        queryControlPanel.add(queryButton);
        
        RootPanel.get("ss_row_select").add(rowSelect);
        RootPanel.get("ss_column_select").add(columnSelect);
        RootPanel.get("ss_swap").add(swapLink);
        RootPanel.get("ss_query_controls").add(queryControlPanel);
        RootPanel.get("ss_actions").add(actionsPanel);
        RootPanel.get("ss_spreadsheet").add(spreadsheet);
        jobCompletionPanel = RootPanel.get("ss_job_completion");
        
        Window.addWindowResizeListener(new WindowResizeListener() {
            public void onWindowResized(int width, int height) {
                if(spreadsheet.isVisible())
                    spreadsheet.fillWindow(true);
            } 
        });
        
        setupDrilldownMap();
    }
    
    protected TestSet getWholeTableTestSet() {
        boolean isSingleTest = spreadsheetProcessor.getNumTotalTests() == 1;
        return new ConditionTestSet(isSingleTest, commonPanel.getSavedCondition());
    }

    protected void setupDrilldownMap() {
        drilldownMap.put("platform", new String[] {"hostname", "test_name"});
        drilldownMap.put("hostname", new String[] {"job_tag", "status"});
        drilldownMap.put("job_tag", new String[] {"job_tag"});
        
        drilldownMap.put("kernel", new String[] {"test_name", "status"});
        drilldownMap.put("test_name", new String[] {"job_name", "job_tag"});
        
        drilldownMap.put("status", new String[] {"reason", "job_tag"});
        drilldownMap.put("reason", new String[] {"job_tag"});
        
        drilldownMap.put("job_owner", new String[] {"job_name", "job_tag"});
        drilldownMap.put("job_name", new String[] {"job_tag"});
        
        drilldownMap.put("test_finished_time", new String[] {"status", "job_tag"});
        drilldownMap.put("DATE(test_finished_time)", 
                         new String[] {"test_finished_time", "job_tag"});
    }
    
    private Header getSelectedHeader(HeaderSelect list) {
        Header selectedFields = new HeaderImpl();
        for (Item item : list.getSelectedItems()) {
            selectedFields.add(item.value);
        }
        return selectedFields;
    }
    
    protected void setSelectedHeader(HeaderSelect list, Header fields) {
        list.selectItemsByValue(fields);
    }

    @Override
    public void refresh() {
        notYetQueried = false;
        spreadsheet.setVisible(false);
        selectionManager.clearSelection();
        spreadsheet.clear();
        setJobCompletionHtml("&nbsp");
        
        String condition = commonPanel.getSavedCondition();
        if (!currentShowIncomplete) {
            if (!condition.equals("")) {
                condition = "(" + condition + ") AND ";
            }
            condition += "status != 'RUNNING'";
        }
        final String finalCondition = condition;
        
        setLoading(true);
        spreadsheetProcessor.refresh(currentRowFields, currentColumnFields, finalCondition,
                                     new Command() {
            public void execute() {
                if (isJobFilteringCondition(finalCondition)) {
                    showCompletionPercentage(finalCondition);
                } else {
                    setLoading(false);
                }
            }
        });
    }

    public void doQuery() {
        Header rows = getSelectedHeader(rowSelect), columns = getSelectedHeader(columnSelect);
        if (rows.isEmpty() || columns.isEmpty()) {
            NotifyManager.getInstance().showError("You must select row and column fields");
            return;
        }
        currentRowFields = getSelectedHeader(rowSelect);
        currentColumnFields = getSelectedHeader(columnSelect);
        currentShowIncomplete = showIncomplete.isChecked();
        saveCondition();
        refresh();
    }

    private void showCompletionPercentage(String condition) {
        rpcProxy.rpcCall("get_job_ids", TkoUtils.getConditionParams(condition), 
                         new JsonRpcCallback() {
            @Override
            public void onSuccess(JSONValue result) {
                finishShowCompletionPercentage(result.isArray());
                setLoading(false);
            }

            @Override
            public void onError(JSONObject errorObject) {
                super.onError(errorObject);
                setLoading(false);
            }
        });
    }

    private void finishShowCompletionPercentage(JSONArray jobIds) {
        final int jobCount = jobIds.size();
        if (jobCount == 0) {
            return;
        }
        
        JSONObject args = new JSONObject();
        args.put("job__id__in", jobIds);
        afeRpcProxy.rpcCall("get_hqe_percentage_complete", args, new JsonRpcCallback() {
            @Override
            public void onSuccess(JSONValue result) {
                int percentage = (int) (result.isNumber().doubleValue() * 100);
                StringBuilder message = new StringBuilder("Matching ");
                if (jobCount == 1) {
                    message.append("job is ");
                } else {
                    message.append("jobs are ");
                }
                message.append(percentage);
                message.append("% complete");
                setJobCompletionHtml(message.toString());
            }
        });
    }
    
    private void setJobCompletionHtml(String html) {
        jobCompletionPanel.clear();
        jobCompletionPanel.add(new HTML(html));
    }

    private boolean isJobFilteringCondition(String condition) {
        return condition.indexOf("job_tag") != -1;
    }

    public void onCellClicked(CellInfo cellInfo) {
        Event event = Event.getCurrentEvent();
        TestSet testSet = getTestSet(cellInfo);
        DrilldownType drilldownType = getDrilldownType(cellInfo);
        if (RightClickTable.isRightClick(event)) {
            if (!selectionManager.isEmpty()) {
                testSet = getTestSet(selectionManager.getSelectedCells());
                drilldownType = DrilldownType.DRILLDOWN_BOTH;
            }
            ContextMenu menu = getContextMenu(testSet, drilldownType);
            menu.showAtWindow(event.getClientX(), event.getClientY());
            return;
        }
        
        if (event.getCtrlKey()) {
            selectionManager.toggleSelected(cellInfo);
            return;
        }
        
        if (testSet.isSingleTest()) {
            TkoUtils.getTestId(testSet, listener);
            return;
        }
        
        doDrilldown(testSet, 
                    getDefaultDrilldownRow(drilldownType), 
                    getDefaultDrilldownColumn(drilldownType));
    }

    private DrilldownType getDrilldownType(CellInfo cellInfo) {
        if (cellInfo.row == null) {
            // column header
            return DrilldownType.DRILLDOWN_COLUMN;
        }
        if (cellInfo.column == null) {
            // row header
            return DrilldownType.DRILLDOWN_ROW;
        }
        return DrilldownType.DRILLDOWN_BOTH;
    }

    private TestSet getTestSet(CellInfo cellInfo) {
        boolean isSingleTest = cellInfo.testCount == 1;
        ConditionTestSet testSet = new ConditionTestSet(isSingleTest, 
                                                        commonPanel.getSavedCondition());
        
        if (cellInfo.row != null) {
            setSomeFields(testSet, currentRowFields, cellInfo.row);
        }
        if (cellInfo.column != null) {
            setSomeFields(testSet, currentColumnFields, cellInfo.column);
        }
        return testSet;
    }
    
    private void setSomeFields(ConditionTestSet testSet, Header allFields, Header values) {
        List<String> usedFields = new UnmodifiableSublistView<String>(allFields, 0, values.size());
        testSet.setFields(usedFields, values);
    }
    
    private TestSet getTestSet(List<CellInfo> cells) {
        CompositeTestSet tests = new CompositeTestSet();
        for (CellInfo cell : cells) {
            tests.add(getTestSet(cell));
        }
        return tests;
    }

    private void doDrilldown(TestSet tests, String newRowField, String newColumnField) {
        commonPanel.refineCondition(tests);
        currentRowFields = HeaderImpl.fromBaseType(Utils.wrapObjectWithList(newRowField));
        currentColumnFields = HeaderImpl.fromBaseType(Utils.wrapObjectWithList(newColumnField));
        updateWidgets();
        doQuery();
        updateHistory();
    }

    private String getDefaultDrilldownRow(DrilldownType type) {
        return getDrilldownRows(type)[0];
    }
    
    private String getDefaultDrilldownColumn(DrilldownType type) {
        return getDrilldownColumns(type)[0];
    }

    private ContextMenu getContextMenu(final TestSet tests, DrilldownType drilldownType) {
        TestContextMenu menu = new TestContextMenu(tests, listener);
        
        if (!menu.addViewDetailsIfSingleTest()) {
            MenuBar drilldownMenu = menu.addSubMenuItem("Drill down");
            fillDrilldownMenu(tests, drilldownType, drilldownMenu);
        }
        
        menu.addItem("View in table", new Command() {
            public void execute() {
                switchToTable(tests, false);
            }
        });
        menu.addItem("Triage failures", new Command() {
            public void execute() {
                switchToTable(tests, true);
            }
        });
        
        menu.addLabelItems();
        return menu;
    }

    private void fillDrilldownMenu(final TestSet tests, DrilldownType drilldownType, MenuBar menu) {
        for (final String rowField : getDrilldownRows(drilldownType)) {
            for (final String columnField : getDrilldownColumns(drilldownType)) {
                if (rowField.equals(columnField)) {
                    continue;
                }
                menu.addItem(rowField + " vs. " + columnField, new Command() {
                    public void execute() {
                        doDrilldown(tests, rowField, columnField);
                    }
                });
            }
        }
    }

    private String[] getDrilldownFields(Header fields, DrilldownType type,
                                        DrilldownType otherType) {
        String lastField = fields.get(fields.size() - 1);
        if (type == otherType) {
            return new String[] {lastField};
        } else {
            return drilldownMap.get(lastField);
        }
    }

    private String[] getDrilldownRows(DrilldownType type) {
        return getDrilldownFields(currentRowFields, type, DrilldownType.DRILLDOWN_COLUMN);
    }
    
    private String[] getDrilldownColumns(DrilldownType type) {
        return getDrilldownFields(currentColumnFields, type, DrilldownType.DRILLDOWN_ROW);
    }
    
    private void updateWidgets() {
        setSelectedHeader(rowSelect, currentRowFields);
        setSelectedHeader(columnSelect, currentColumnFields);
        showIncomplete.setChecked(currentShowIncomplete);
    }

    @Override
    protected Map<String, String> getHistoryArguments() {
        Map<String, String> arguments = super.getHistoryArguments();
        if (!notYetQueried) {
            arguments.put("row", headerToString(currentRowFields));
            arguments.put("column", headerToString(currentColumnFields));
            arguments.put("show_incomplete", Boolean.toString(currentShowIncomplete));
            commonPanel.addHistoryArguments(arguments);
        }
        return arguments;
    }

    private String headerToString(Header header) {
        return Utils.joinStrings(",", header);
    }
    
    @Override
    public void handleHistoryArguments(Map<String, String> arguments) {
        super.handleHistoryArguments(arguments);
        commonPanel.handleHistoryArguments(arguments);
        
        String rows = arguments.get("row"), columns = arguments.get("column");
        currentRowFields = HeaderImpl.fromBaseType(Arrays.asList(rows.split(",")));
        currentColumnFields = HeaderImpl.fromBaseType(Arrays.asList(columns.split(",")));
        currentShowIncomplete = Boolean.valueOf(arguments.get("show_incomplete"));
        
        updateWidgets();
    }

    @Override
    protected void fillDefaultHistoryValues(Map<String, String> arguments) {
        Utils.setDefaultValue(arguments, "row", DEFAULT_ROW);
        Utils.setDefaultValue(arguments, "column", DEFAULT_COLUMN);
        Utils.setDefaultValue(arguments, "show_incomplete", Boolean.toString(currentShowIncomplete));
    }

    private void switchToTable(final TestSet tests, boolean isTriageView) {
        commonPanel.refineCondition(tests);
        listener.onSwitchToTable(isTriageView);
    }

    public ContextMenu getActionMenu() {
        TestSet tests;
        if (selectionManager.isEmpty()) {
            tests = getWholeTableTestSet();
        } else {
            tests = getTestSet(selectionManager.getSelectedCells());
        }
        return getContextMenu(tests, DrilldownType.DRILLDOWN_BOTH);
    }

    public void onSelectAll(boolean ignored) {
        selectionManager.selectAll();
    }

    public void onSelectNone() {
        selectionManager.clearSelection();
    }

    @Override
    protected boolean hasFirstQueryOccurred() {
        return !notYetQueried;
    }

    private void setLoading(boolean loading) {
        queryButton.setEnabled(!loading);
        NotifyManager.getInstance().setLoading(loading);
    }
}
