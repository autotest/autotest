package autotest.afe;

import autotest.common.JsonRpcCallback;
import autotest.common.JsonRpcProxy;
import autotest.common.table.ListFilter;
import autotest.common.table.SelectionManager;
import autotest.common.table.TableDecorator;
import autotest.common.table.DynamicTable.DynamicTableListener;
import autotest.common.ui.ContextMenu;
import autotest.common.ui.NotifyManager;
import autotest.common.ui.TabView;
import autotest.common.ui.TableActionsPanel.TableActionsListener;

import com.google.gwt.event.dom.client.ClickEvent;
import com.google.gwt.event.dom.client.ClickHandler;
import com.google.gwt.i18n.client.DateTimeFormat;
import com.google.gwt.json.client.JSONArray;
import com.google.gwt.json.client.JSONNumber;
import com.google.gwt.json.client.JSONObject;
import com.google.gwt.json.client.JSONString;
import com.google.gwt.json.client.JSONValue;
import com.google.gwt.user.client.Command;
import com.google.gwt.user.client.ui.Button;
import com.google.gwt.user.client.ui.FlexTable;
import com.google.gwt.user.client.ui.HasAlignment;
import com.google.gwt.user.client.ui.Label;
import com.google.gwt.user.client.ui.TextBox;
import com.google.gwt.user.client.ui.VerticalPanel;
import com.google.gwt.user.client.ui.Widget;

import java.util.Set;

public class RecurringView extends TabView implements TableActionsListener {
    private static final int RECURRINGRUN_PER_PAGE = 30;
    private static final int DEFAULT_LOOP_DELAY = 3600;
    private static final int DEFAULT_LOOP_COUNT = 1;

    private RecurringSelectListener selectListener;
    private RecurringTable recurringTable;
    private TableDecorator tableDecorator;
    private ListFilter ownerFilter;
    private SelectionManager selectionManager;
    private VerticalPanel createRecurringPanel;
    private Label jobIdLbl = new Label("");
    private TextBox startDate = new TextBox();
    private TextBox loopDelay = new TextBox();
    private TextBox loopCount = new TextBox();
    private FlexTable createRecurTable;
    
    private JsonRpcProxy rpcProxy = JsonRpcProxy.getProxy();
    
    interface RecurringSelectListener {
        public void onRecurringSelected(int schedId);
    }

    @Override
    public String getElementId() {
        return "recurring_list";
    }

    @Override
    public void refresh() {
        super.refresh();
        recurringTable.refresh();
    }

    public RecurringView(RecurringSelectListener listener) {
        selectListener = listener;
    }
    
    @Override
    public void initialize() {
        recurringTable = new RecurringTable();
        
        recurringTable.setRowsPerPage(RECURRINGRUN_PER_PAGE);
        recurringTable.setClickable(true);
        recurringTable.addListener(new DynamicTableListener() {
            public void onRowClicked(int rowIndex, JSONObject row) {
                JSONObject job = row.get("job").isObject();
                int jobId = (int) job.get("id").isNumber().doubleValue();
                selectListener.onRecurringSelected(jobId);
            }
            
            public void onTableRefreshed() {}
        });

        tableDecorator = new TableDecorator(recurringTable);
        tableDecorator.addPaginators();
        selectionManager = tableDecorator.addSelectionManager(false);
        recurringTable.setWidgetFactory(selectionManager);
        tableDecorator.addTableActionsPanel(this, true);
        addWidget(tableDecorator, "recurring_table");


        ownerFilter = AfeUtils.getUserFilter("owner__login");
        recurringTable.addFilter(ownerFilter);
        addWidget(ownerFilter.getWidget(), "recurring_user_list");

        initRecurringPanel();

        addWidget(createRecurringPanel, "recurring_create_panel");
    }

    public ContextMenu getActionMenu() {
        ContextMenu menu = new ContextMenu();
        menu.addItem("Remove recurring runs", new Command() {
            public void execute() {
                removeSelectedRecurring();
            }
        });
        return menu;
    }

    private void initRecurringPanel() {
        createRecurTable = new FlexTable();

        Label createLbl = new Label("Creating recurring job");
        Button createBtn = new Button("Create recurring job");
        Button resetBtn = new Button("Reset");
        Button cancelBtn = new Button("Cancel");

        createRecurringPanel = new VerticalPanel();
        createRecurringPanel.setVisible(false);

        createLbl.setStyleName("title");
        createLbl.setHorizontalAlignment(HasAlignment.ALIGN_CENTER);

        setCreateTableRow(0, "Template Job Id:", jobIdLbl);
        setCreateTableRow(1, "Start time (on server):", startDate);
        setCreateTableRow(2, "Loop delay (in sec.):", loopDelay);
        setCreateTableRow(3, "Loop count:", loopCount);

        createRecurTable.setWidget(4, 0, createBtn);
        createRecurTable.setWidget(4, 1, resetBtn);
        createRecurTable.setWidget(4, 2, cancelBtn);

        createRecurringPanel.add(createLbl);
        createRecurringPanel.add(createRecurTable);

        resetBtn.addClickHandler(new ClickHandler() {
            public void onClick(ClickEvent event) {
                resetCreate();
            }
        });

        createBtn.addClickHandler(new ClickHandler() {
            public void onClick(ClickEvent event) {
                submitRecurringJob();
            }
        });

        cancelBtn.addClickHandler(new ClickHandler() {
            public void onClick(ClickEvent event) {
                createRecurringPanel.setVisible(false);
            }
        });

    }

    private void setCreateTableRow(int row, String name, Widget control) {
        createRecurTable.setText(row, 0, name);
        createRecurTable.setWidget(row, 1, control);
        createRecurTable.getFlexCellFormatter().setStyleName(row, 0, "field-name");
    }

    public void createRecurringJob(int jobId) {
        createRecurringPanel.setVisible(true);
        jobIdLbl.setText(Integer.toString(jobId));
        resetCreate();
    }

    private void submitRecurringJob() {
        final int delayValue, countValue;
        try {
            delayValue = AfeUtils.parsePositiveIntegerInput(loopDelay.getText(),
                                                            "loop delay");
            countValue = AfeUtils.parsePositiveIntegerInput(loopCount.getText(),
                                                            "loop count");
           checkDate();
        } catch (IllegalArgumentException exc) {
            return;
        }

        JSONObject args = new JSONObject();
        args.put("job_id", new JSONNumber(Integer.parseInt(jobIdLbl.getText())));
        args.put("start_date", new JSONString(startDate.getText()));
        args.put("loop_period", new JSONNumber(delayValue));
        args.put("loop_count", new JSONNumber(countValue));

        rpcProxy.rpcCall("create_recurring_run", args, new JsonRpcCallback() {
            @Override
            public void onSuccess(JSONValue result) {
                int id = (int) result.isNumber().doubleValue();
                createRecurringPanel.setVisible(false);
                NotifyManager.getInstance().showMessage("Recurring run " +
                                                        Integer.toString(id) +
                                                        " created");
                refresh();
            }
        });
    }

    private void resetCreate() {
        getServerTime();
        loopDelay.setText(Integer.toString(DEFAULT_LOOP_DELAY));
        loopCount.setText(Integer.toString(DEFAULT_LOOP_COUNT));
    }

    private void getServerTime() {
        rpcProxy.rpcCall("get_server_time", null, new JsonRpcCallback() {
            @Override
            public void onSuccess(JSONValue result) {
                String sTime = result.isString().stringValue();
                startDate.setText(sTime);
            }
        });
    }

    private void checkDate() {
        try {
            DateTimeFormat fmt = DateTimeFormat.getFormat("yyyy-MM-dd HH:mm");
            fmt.parse(startDate.getText());
        }
        catch (IllegalArgumentException exc) {
            String error = "Please enter a correct date/time " +
                           "format: yyyy-MM-dd HH:mm";
            NotifyManager.getInstance().showError(error);
            throw new IllegalArgumentException();
        }
    }

    private void removeSelectedRecurring() {
        Set<JSONObject> selectedSet = selectionManager.getSelectedObjects();
        if (selectedSet.isEmpty()) {
            NotifyManager.getInstance().showError("No recurring run selected");
            return;
        }

        JSONArray ids = new JSONArray();
        for(JSONObject jsonObj : selectedSet) {
            ids.set(ids.size(), jsonObj.get("id"));
        }

        JSONObject params = new JSONObject();
        params.put("id__in", ids);
        callRemove(params);
    }

    private void callRemove(JSONObject params) {
        JsonRpcProxy rpcProxy = JsonRpcProxy.getProxy();
        rpcProxy.rpcCall("delete_recurring_runs", params,
                         new JsonRpcCallback() {
            @Override
            public void onSuccess(JSONValue result) {
                    NotifyManager.getInstance().showMessage("Recurring runs " +
                                                            "removed");
                    refresh();
            }
        });
    }
}
