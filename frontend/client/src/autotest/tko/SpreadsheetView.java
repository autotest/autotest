package autotest.tko;

import autotest.common.JsonRpcCallback;
import autotest.common.JsonRpcProxy;
import autotest.common.Utils;
import autotest.common.CustomHistory.HistoryToken;
import autotest.common.spreadsheet.Spreadsheet;
import autotest.common.spreadsheet.SpreadsheetSelectionManager;
import autotest.common.spreadsheet.Spreadsheet.CellInfo;
import autotest.common.spreadsheet.Spreadsheet.SpreadsheetListener;
import autotest.common.ui.ContextMenu;
import autotest.common.ui.NotifyManager;
import autotest.common.ui.TableActionsPanel;
import autotest.common.ui.TableActionsPanel.TableActionsWithExportCsvListener;
import autotest.common.ui.TableSelectionPanel.SelectionPanelListener;
import autotest.tko.CommonPanel.CommonPanelListener;
import autotest.tko.TableView.TableSwitchListener;
import autotest.tko.TableView.TableViewConfig;
import autotest.tko.TkoSpreadsheetUtils.DrilldownType;

import com.google.gwt.event.dom.client.ClickEvent;
import com.google.gwt.event.dom.client.ClickHandler;
import com.google.gwt.event.logical.shared.ResizeEvent;
import com.google.gwt.event.logical.shared.ResizeHandler;
import com.google.gwt.event.logical.shared.ValueChangeEvent;
import com.google.gwt.event.logical.shared.ValueChangeHandler;
import com.google.gwt.json.client.JSONArray;
import com.google.gwt.json.client.JSONObject;
import com.google.gwt.json.client.JSONString;
import com.google.gwt.json.client.JSONValue;
import com.google.gwt.user.client.Command;
import com.google.gwt.user.client.Event;
import com.google.gwt.user.client.History;
import com.google.gwt.user.client.Window;
import com.google.gwt.user.client.ui.Anchor;
import com.google.gwt.user.client.ui.Button;
import com.google.gwt.user.client.ui.CheckBox;
import com.google.gwt.user.client.ui.HTML;
import com.google.gwt.user.client.ui.MenuBar;
import com.google.gwt.user.client.ui.Panel;
import com.google.gwt.user.client.ui.SimplePanel;
import com.google.gwt.user.client.ui.VerticalPanel;

import java.util.HashMap;
import java.util.List;
import java.util.Map;

public class SpreadsheetView extends ConditionTabView
                             implements SpreadsheetListener, TableActionsWithExportCsvListener,
                                        CommonPanelListener, SelectionPanelListener {
    private static final String HISTORY_ONLY_LATEST = "show_only_latest";
    public static final String DEFAULT_ROW = "kernel";
    public static final String DEFAULT_COLUMN = "platform";
    public static final String DEFAULT_DRILLDOWN = "job_tag";

    private static final String HISTORY_SHOW_INCOMPLETE = "show_incomplete";
    private static final String HISTORY_COLUMN = "column";
    private static final String HISTORY_ROW = "row";
    private static final String HISTORY_CONTENT = "content";

    private static JsonRpcProxy rpcProxy = JsonRpcProxy.getProxy();
    private static JsonRpcProxy afeRpcProxy = JsonRpcProxy.getProxy(JsonRpcProxy.AFE_BASE_URL);
    private TableSwitchListener listener;
    protected Map<String,String[]> drilldownMap = new HashMap<String,String[]>();
    private HeaderFieldCollection headerFields = commonPanel.getHeaderFields();

    private SpreadsheetHeaderSelect rowSelect = new SpreadsheetHeaderSelect(headerFields);
    private SpreadsheetHeaderSelectorView rowSelectDisplay = new SpreadsheetHeaderSelectorView();
    private SpreadsheetHeaderSelect columnSelect = new SpreadsheetHeaderSelect(headerFields);
    private SpreadsheetHeaderSelectorView columnSelectDisplay = new SpreadsheetHeaderSelectorView();
    private ContentSelect contentSelect = new ContentSelect(headerFields);
    private CheckBox showIncomplete = new CheckBox("Show incomplete tests");
    private CheckBox showOnlyLatest = new CheckBox("Show only latest test per cell");
    private Button queryButton = new Button("Query");
    private TestGroupDataSource normalDataSource = TestGroupDataSource.getStatusCountDataSource();
    private TestGroupDataSource latestDataSource = TestGroupDataSource.getLatestTestsDataSource();
    private Spreadsheet spreadsheet = new Spreadsheet();
    private SpreadsheetDataProcessor spreadsheetProcessor =
        new SpreadsheetDataProcessor(spreadsheet);
    private SpreadsheetSelectionManager selectionManager =
        new SpreadsheetSelectionManager(spreadsheet, null);
    private TableActionsPanel actionsPanel = new TableActionsPanel(false);
    private Panel jobCompletionPanel = new SimplePanel();
    private boolean currentShowIncomplete, currentShowOnlyLatest;
    private boolean notYetQueried = true;

    public SpreadsheetView(TableSwitchListener listener) {
        this.listener = listener;
        commonPanel.addListener(this);
        rowSelect.bindDisplay(rowSelectDisplay);
        columnSelect.bindDisplay(columnSelectDisplay);
    }

    @Override
    public String getElementId() {
        return "spreadsheet_view";
    }

    @Override
    public void initialize() {
        super.initialize();

        setHeaderSelectField(rowSelect, DEFAULT_ROW);
        setHeaderSelectField(columnSelect, DEFAULT_COLUMN);

        actionsPanel.setActionsWithCsvListener(this);
        actionsPanel.setSelectionListener(this);
        actionsPanel.setVisible(false);

        contentSelect.addValueChangeHandler(new ValueChangeHandler<Boolean>() {
            public void onValueChange(ValueChangeEvent<Boolean> event) {
                if (event.getValue()) {
                    showOnlyLatest.setValue(true);
                    showOnlyLatest.setEnabled(false);
                } else {
                    showOnlyLatest.setEnabled(true);
                }
            }
        });

        updateViewFromState();

        queryButton.addClickHandler(new ClickHandler() {
            public void onClick(ClickEvent event) {
                doQueryWithCommonPanelCheck();
                updateHistory();
            }
        });

        spreadsheet.setVisible(false);
        spreadsheet.setListener(this);

        Anchor swapLink = new Anchor("swap");
        swapLink.addClickHandler(new ClickHandler() {
            public void onClick(ClickEvent event) {
                SpreadsheetHeaderSelect.State rowState = rowSelect.getStateFromView();
                rowSelect.loadFromState(columnSelect.getStateFromView());
                columnSelect.loadFromState(rowState);
            }
        });

        Panel filterOptions = new VerticalPanel();
        filterOptions.add(showIncomplete);
        filterOptions.add(showOnlyLatest);

        addWidget(filterOptions, "ss_filter_options");
        addWidget(rowSelectDisplay, "ss_row_select");
        addWidget(columnSelectDisplay, "ss_column_select");
        addWidget(contentSelect, "ss_additional_content");
        addWidget(swapLink, "ss_swap");
        addWidget(queryButton, "ss_query_controls");
        addWidget(actionsPanel, "ss_actions");
        addWidget(spreadsheet, "ss_spreadsheet");
        addWidget(jobCompletionPanel, "ss_job_completion");

        Window.addResizeHandler(new ResizeHandler() {
            public void onResize(ResizeEvent event) {
                if(spreadsheet.isVisible()) {
                    spreadsheet.fillWindow(true);
                }
            }
        });

        setupDrilldownMap();
    }

    private void setHeaderSelectField(SpreadsheetHeaderSelect headerSelect,
                                      String defaultField) {
        headerSelect.setSelectedItem(headerFields.getFieldBySqlName(defaultField));
    }

    protected TestSet getWholeTableTestSet() {
        boolean isSingleTest = spreadsheetProcessor.getNumTotalTests() == 1;
        if (isSingleTest) {
            return getTestSet(spreadsheetProcessor.getLastCellInfo());
        }

        if (currentShowOnlyLatest) {
            List<Integer> testIndices = spreadsheet.getAllTestIndices();
            String filter = "test_idx IN (" + Utils.joinStrings(",", testIndices) + ")";
            ConditionTestSet tests = new ConditionTestSet();
            tests.addCondition(filter);
            return tests;
        }

        return new ConditionTestSet(getFullConditionArgs());
    }

    protected void setupDrilldownMap() {
        drilldownMap.put("platform", new String[] {"hostname", "test_name"});
        drilldownMap.put("hostname", new String[] {"job_tag", "status"});

        drilldownMap.put("kernel", new String[] {"test_name", "status"});
        drilldownMap.put("test_name", new String[] {"subdir", "job_name", "job_tag"});

        drilldownMap.put("status", new String[] {"reason", "job_tag"});

        drilldownMap.put("job_owner", new String[] {"job_name", "job_tag"});

        drilldownMap.put("test_finished_time", new String[] {"status", "job_tag"});
        drilldownMap.put("DATE(test_finished_time)",
                         new String[] {"test_finished_time", "job_tag"});

        drilldownMap.put("job_tag", new String[] {"subdir"});
    }

    protected void setSelectedHeader(HeaderSelect list, List<HeaderField> fields) {
        list.setSelectedItems(fields);
    }

    @Override
    public void refresh() {
        notYetQueried = false;
        actionsPanel.setVisible(true);
        spreadsheet.setVisible(false);
        selectionManager.clearSelection();
        spreadsheet.clear();
        setJobCompletionHtml("&nbsp");

        final JSONObject condition = getFullConditionArgs();

        contentSelect.addToCondition(condition);

        setLoading(true);
        if (currentShowOnlyLatest) {
            spreadsheetProcessor.setDataSource(latestDataSource);
        } else {
            spreadsheetProcessor.setDataSource(normalDataSource);
        }
        spreadsheetProcessor.setHeaders(rowSelect.getSelectedItems(),
                                        columnSelect.getSelectedItems(),
                                        getQueryParameters());
        spreadsheetProcessor.refresh(condition, new Command() {
            public void execute() {
                condition.put("extra_info", null);

                if (isJobFilteringCondition(condition)) {
                    showCompletionPercentage(condition);
                } else {
                    setLoading(false);
                }
            }
        });
    }

    private JSONObject getQueryParameters() {
        JSONObject parameters = new JSONObject();
        rowSelect.addQueryParameters(parameters);
        columnSelect.addQueryParameters(parameters);
        return parameters;
    }

    private JSONObject getFullConditionArgs() {
        JSONObject args = commonPanel.getConditionArgs();
        String condition = TkoUtils.getSqlCondition(args);
        if (!condition.equals("")) {
            condition = "(" + condition + ") AND ";
        }
        condition += "status != 'TEST_NA'";
        if (!currentShowIncomplete) {
            condition += " AND status != 'RUNNING'";
        }
        args.put("extra_where", new JSONString(condition));
        return args;
    }

    private void updateStateFromView() {
        rowSelect.updateStateFromView();
        columnSelect.updateStateFromView();
        currentShowIncomplete = showIncomplete.getValue();
        currentShowOnlyLatest = showOnlyLatest.getValue();
        commonPanel.updateStateFromView();
    }

    @Override
    public void doQuery() {
        List<HeaderField> rows = rowSelect.getSelectedItems();
        List<HeaderField> columns = columnSelect.getSelectedItems();
        if (rows.isEmpty() || columns.isEmpty()) {
            NotifyManager.getInstance().showError("You must select row and column fields");
            return;
        }

        updateStateFromView();
        refresh();
    }

    private void showCompletionPercentage(JSONObject condition) {
        rpcProxy.rpcCall("get_job_ids", condition, new JsonRpcCallback() {
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

    private boolean isJobFilteringCondition(JSONObject condition) {
        return TkoUtils.getSqlCondition(condition).indexOf("job_tag") != -1;
    }

    @Override
    public void onCellClicked(CellInfo cellInfo, boolean isRightClick) {
        Event event = Event.getCurrentEvent();
        TestSet testSet = getTestSet(cellInfo);
        DrilldownType drilldownType = TkoSpreadsheetUtils.getDrilldownType(cellInfo);
        if (isRightClick) {
            if (!selectionManager.isEmpty()) {
                testSet = getTestSet(selectionManager.getSelectedCells());
                drilldownType = DrilldownType.DRILLDOWN_BOTH;
            }
            ContextMenu menu = getContextMenu(testSet, drilldownType);
            menu.showAtWindow(event.getClientX(), event.getClientY());
            return;
        }

        if (isSelectEvent(event)) {
            selectionManager.toggleSelected(cellInfo);
            return;
        }

        HistoryToken historyToken;
        if (testSet.isSingleTest()) {
            historyToken = listener.getSelectTestHistoryToken(testSet.getTestIndex());
        } else {
            historyToken = getDrilldownHistoryToken(testSet,
                                                    getDefaultDrilldownRow(drilldownType),
                                                    getDefaultDrilldownColumn(drilldownType));
        }
        openHistoryToken(historyToken);
    }

    private TestSet getTestSet(CellInfo cellInfo) {
        return TkoSpreadsheetUtils.getTestSet(cellInfo, getFullConditionArgs(),
                rowSelect.getSelectedItems(), columnSelect.getSelectedItems());
    }

    private TestSet getTestSet(List<CellInfo> cells) {
        CompositeTestSet tests = new CompositeTestSet();
        for (CellInfo cell : cells) {
            tests.add(getTestSet(cell));
        }
        return tests;
    }

    private HistoryToken getDrilldownHistoryToken(TestSet tests, String newRowField,
                                                  String newColumnField) {
        saveHistoryState();
        commonPanel.refineCondition(tests);
        rowSelect.setSelectedItem(headerFields.getFieldBySqlName(newRowField));
        columnSelect.setSelectedItem(headerFields.getFieldBySqlName(newColumnField));
        HistoryToken historyArguments = getHistoryArguments();
        restoreHistoryState();
        return historyArguments;
    }

    private void doDrilldown(TestSet tests, String newRowField, String newColumnField) {
        History.newItem(getDrilldownHistoryToken(tests, newRowField, newColumnField).toString());
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

    private String[] getDrilldownFields(List<HeaderField> fields, DrilldownType type,
                                        DrilldownType otherType) {
        HeaderField lastField = fields.get(fields.size() - 1);
        String lastFieldName = lastField.getSqlName();
        if (type == otherType) {
            return new String[] {lastFieldName};
        } else {
            if (lastField instanceof MachineLabelField) {
                // treat machine label fields like platform, for the purpose of default drilldown
                lastFieldName = "platform";
            }
            if (drilldownMap.containsKey(lastFieldName)) {
                return drilldownMap.get(lastFieldName);
            }
            return new String[] {DEFAULT_DRILLDOWN};
        }
    }

    private String[] getDrilldownRows(DrilldownType type) {
        return getDrilldownFields(rowSelect.getSelectedItems(), type,
                                  DrilldownType.DRILLDOWN_COLUMN);
    }

    private String[] getDrilldownColumns(DrilldownType type) {
        return getDrilldownFields(columnSelect.getSelectedItems(), type,
                                  DrilldownType.DRILLDOWN_ROW);
    }

    private void updateViewFromState() {
        rowSelect.updateViewFromState();
        columnSelect.updateViewFromState();
        showIncomplete.setValue(currentShowIncomplete);
        showOnlyLatest.setValue(currentShowOnlyLatest);
        commonPanel.updateViewFromState();
    }

    @Override
    public HistoryToken getHistoryArguments() {
        HistoryToken arguments = super.getHistoryArguments();
        if (!notYetQueried) {
            rowSelect.addHistoryArguments(arguments, HISTORY_ROW);
            columnSelect.addHistoryArguments(arguments, HISTORY_COLUMN);
            contentSelect.addHistoryArguments(arguments, HISTORY_CONTENT);
            arguments.put(HISTORY_SHOW_INCOMPLETE, Boolean.toString(currentShowIncomplete));
            arguments.put(HISTORY_ONLY_LATEST, Boolean.toString(showOnlyLatest.getValue()));
            commonPanel.addHistoryArguments(arguments);
        }
        return arguments;
    }

    @Override
    public void handleHistoryArguments(Map<String, String> arguments) {
        super.handleHistoryArguments(arguments);
        commonPanel.handleHistoryArguments(arguments);
        rowSelect.handleHistoryArguments(arguments, HISTORY_ROW);
        columnSelect.handleHistoryArguments(arguments, HISTORY_COLUMN);
        contentSelect.handleHistoryArguments(arguments, HISTORY_CONTENT);

        currentShowIncomplete = Boolean.valueOf(arguments.get(HISTORY_SHOW_INCOMPLETE));
        currentShowOnlyLatest = Boolean.valueOf(arguments.get(HISTORY_ONLY_LATEST));
        updateViewFromState();
    }

    @Override
    protected void fillDefaultHistoryValues(Map<String, String> arguments) {
        Utils.setDefaultValue(arguments, HISTORY_ROW, DEFAULT_ROW);
        Utils.setDefaultValue(arguments, HISTORY_COLUMN, DEFAULT_COLUMN);
        Utils.setDefaultValue(arguments,
                              HISTORY_ROW + SpreadsheetHeaderSelect.HISTORY_FIXED_VALUES, "");
        Utils.setDefaultValue(arguments,
                              HISTORY_COLUMN + SpreadsheetHeaderSelect.HISTORY_FIXED_VALUES, "");
        Utils.setDefaultValue(arguments, HISTORY_SHOW_INCOMPLETE, Boolean.toString(false));
        Utils.setDefaultValue(arguments, HISTORY_ONLY_LATEST, Boolean.toString(false));
    }

    private void switchToTable(final TestSet tests, boolean isTriageView) {
        commonPanel.refineCondition(tests);
        TableViewConfig config;
        if (isTriageView) {
            config = TableViewConfig.TRIAGE;
            refineConditionForTriage();
        } else {
            config = TableViewConfig.DEFAULT;
        }
        listener.onSwitchToTable(config);
    }

    private void refineConditionForTriage() {
        commonPanel.refineCondition("status != 'GOOD'");
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

    public void onExportCsv() {
        JSONObject params = new JSONObject();
        contentSelect.addToCondition(params);
        TkoUtils.doCsvRequest(spreadsheetProcessor.getDataSource(),
                              spreadsheetProcessor.getCurrentQuery(), params);
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

    @Override
    public void onSetControlsVisible(boolean visible) {
        TkoUtils.setElementVisible("ss_all_controls", visible);
        if (isTabVisible()) {
            spreadsheet.fillWindow(true);
        }
    }

    @Override
    public void onFieldsChanged() {
        rowSelect.refreshFields();
        columnSelect.refreshFields();
        contentSelect.refreshFields();
    }
}
