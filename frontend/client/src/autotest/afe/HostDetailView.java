package autotest.afe;

import autotest.afe.create.CreateJobViewPresenter.JobCreateListener;
import autotest.common.SimpleCallback;
import autotest.common.StaticDataRepository;
import autotest.common.Utils;
import autotest.common.table.DataSource;
import autotest.common.table.DataSource.DataCallback;
import autotest.common.table.DataSource.Query;
import autotest.common.table.DataSource.SortDirection;
import autotest.common.table.DataTable;
import autotest.common.table.DynamicTable;
import autotest.common.table.DynamicTable.DynamicTableListener;
import autotest.common.table.JSONObjectSet;
import autotest.common.table.RpcDataSource;
import autotest.common.table.SelectionManager;
import autotest.common.table.SelectionManager.SelectableRowFilter;
import autotest.common.table.SimpleFilter;
import autotest.common.table.TableDecorator;
import autotest.common.ui.ContextMenu;
import autotest.common.ui.DetailView;
import autotest.common.ui.NotifyManager;
import autotest.common.ui.TableActionsPanel.TableActionsListener;

import com.google.gwt.event.dom.client.ClickEvent;
import com.google.gwt.event.dom.client.ClickHandler;
import com.google.gwt.json.client.JSONArray;
import com.google.gwt.json.client.JSONBoolean;
import com.google.gwt.json.client.JSONObject;
import com.google.gwt.json.client.JSONString;
import com.google.gwt.json.client.JSONValue;
import com.google.gwt.user.client.Command;
import com.google.gwt.user.client.ui.Button;
import com.google.gwt.user.client.ui.CheckBox;
import com.google.gwt.user.client.ui.TextBox;
import com.google.gwt.user.client.ui.HorizontalPanel;
import com.google.gwt.user.client.Window;

import java.util.Date;
import java.util.List;
import java.util.Set;

public class HostDetailView extends DetailView
                            implements DataCallback, TableActionsListener, SelectableRowFilter {
    private static final StaticDataRepository staticData = StaticDataRepository.getRepository();
    private static final JSONObject user = staticData.getData("current_user").isObject();
    private static final String[][] HOST_JOBS_COLUMNS = {
            {DataTable.WIDGET_COLUMN, ""}, {"type", "Type"}, {"job__id", "Job ID"},
            {"job_owner", "Job Owner"}, {"job_name", "Job Name"}, {"profile", "Profile"},
            {"started_on", "Time started"}, {"status", "Status"}
    };
    public static final int JOBS_PER_PAGE = 20;

    public interface HostDetailListener {
        public void onJobSelected(int jobId);
    }

    private static class HostQueueEntryDataSource extends RpcDataSource {
        public HostQueueEntryDataSource() {
            super("get_host_queue_entries", "get_num_host_queue_entries");
        }

        @Override
        protected List<JSONObject> handleJsonResult(JSONValue result) {
            List<JSONObject> resultArray = super.handleJsonResult(result);
            for (JSONObject row : resultArray) {
                // get_host_queue_entries() doesn't return type, so fill it in for consistency with
                // get_host_queue_entries_and_special_tasks()
                row.put("type", new JSONString("Job"));
            }
            return resultArray;
        }
    }

    private static class HostJobsTable extends DynamicTable {
        private static final DataSource normalDataSource = new HostQueueEntryDataSource();
        private static final DataSource dataSourceWithSpecialTasks =
            new RpcDataSource("get_host_queue_entries_and_special_tasks",
                              "get_num_host_queue_entries_and_special_tasks");

        private SimpleFilter hostFilter = new SimpleFilter();
        private String hostname;

        public HostJobsTable() {
            super(HOST_JOBS_COLUMNS, normalDataSource);
            addFilter(hostFilter);
        }

        public void setHostname(String hostname) {
            this.hostname = hostname;
            updateFilter();
        }

        private void updateFilter() {
            String key;
            if (getDataSource() == normalDataSource) {
                key = "host__hostname";
                sortOnColumn("job__id", SortDirection.DESCENDING);
            } else {
                key = "hostname";
                clearSorts();
            }

            hostFilter.clear();
            hostFilter.setParameter(key, new JSONString(hostname));
        }

        public void setSpecialTasksEnabled(boolean enabled) {
            if (enabled) {
                setDataSource(dataSourceWithSpecialTasks);
            } else {
                setDataSource(normalDataSource);
            }

            updateFilter();
        }

        @Override
        protected void preprocessRow(JSONObject row) {
            JSONObject job = row.get("job").isObject();
            JSONString blank = new JSONString("");
            JSONString jobId = blank, owner = blank, name = blank;
            if (job != null) {
                int id = (int) job.get("id").isNumber().doubleValue();
                jobId = new JSONString(Integer.toString(id));
                owner = job.get("owner").isString();
                name = job.get("name").isString();
            }

            row.put("job__id", jobId);
            row.put("job_owner", owner);
            row.put("job_name", name);
        }
    }

    private String hostname = "";
    private DataSource hostDataSource = new HostDataSource();
    private HostJobsTable jobsTable = new HostJobsTable();
    private TableDecorator tableDecorator = new TableDecorator(jobsTable);
    private HostDetailListener hostDetailListener = null;
    private JobCreateListener jobCreateListener = null;
    private SelectionManager selectionManager;

    private JSONObject currentHostObject;

    private Button lockButton = new Button();
    private Button reverifyButton = new Button("Reverify");
    private Button reinstallButton = new Button("Reinstall");
    private Button reserveButton = new Button("Reserve");
    private Button releaseButton = new Button("Release");
    private Button forceReleaseButton = new Button("Force Release");
    private CheckBox showSpecialTasks = new CheckBox();

    public HostDetailView(HostDetailListener hostDetailListener,
                          JobCreateListener jobCreateListener) {
        this.hostDetailListener = hostDetailListener;
        this.jobCreateListener = jobCreateListener;
    }

    @Override
    public String getElementId() {
        return "view_host";
    }

    @Override
    protected String getFetchControlsElementId() {
        return "view_host_fetch_controls";
    }

    @Override
    protected String getDataElementId() {
        return "view_host_data";
    }

    @Override
    protected String getTitleElementId() {
        return "view_host_title";
    }

    @Override
    protected String getNoObjectText() {
        return "No host selected";
    }

    @Override
    protected String getObjectId() {
        return hostname;
    }

    @Override
    protected void setObjectId(String id) {
        if (id.length() == 0) {
            throw new IllegalArgumentException();
        }
        this.hostname = id;
    }

    @Override
    protected void fetchData() {
        JSONObject params = new JSONObject();
        params.put("hostname", new JSONString(hostname));
        params.put("valid_only", JSONBoolean.getInstance(false));
        hostDataSource.query(params, this);
    }

    @Override
    public void handleTotalResultCount(int totalCount) {}

    @Override
    public void onQueryReady(Query query) {
        query.getPage(null, null, null, this);
    }

    public void handlePage(List<JSONObject> data) {
        try {
            currentHostObject = Utils.getSingleObjectFromList(data);
        }
        catch (IllegalArgumentException exc) {
            NotifyManager.getInstance().showError("No such host found");
            resetPage();
            return;
        }

        String lockedText = Utils.jsonToString(currentHostObject.get(HostDataSource.LOCKED_TEXT));
        if (currentHostObject.get("locked").isBoolean().booleanValue()) {
            String lockedBy = Utils.jsonToString(currentHostObject.get("locked_by"));
            String lockedTime = Utils.jsonToString(currentHostObject.get("lock_time"));
            lockedText += ", by " + lockedBy + " on " + lockedTime;
        }

        showField(currentHostObject, "status", "view_host_status");
        showField(currentHostObject, "platform", "view_host_platform");
        showField(currentHostObject, HostDataSource.HOST_ACLS, "view_host_acls");
        showField(currentHostObject, HostDataSource.OTHER_LABELS, "view_host_labels");
        showText(lockedText, "view_host_locked");
        showField(currentHostObject, "protection", "view_host_protection");
        showField(currentHostObject, "current_profile", "view_host_current_profile");

        reserveButton.setVisible(AfeUtils.hostIsEveryoneAccessible(currentHostObject));
        releaseButton.setVisible(AfeUtils.hostIsAclAccessible(currentHostObject));
        forceReleaseButton.setVisible((int)user.get("access_level").isNumber().doubleValue() >= 1);

        String pageTitle = "Host " + hostname;
        updateLockButton();
        displayObjectData(pageTitle);

        jobsTable.setHostname(hostname);
        jobsTable.refresh();
    }

    @Override
    public void initialize() {
        super.initialize();

        jobsTable.setRowsPerPage(JOBS_PER_PAGE);
        jobsTable.setClickable(true);
        jobsTable.addListener(new DynamicTableListener() {
            public void onRowClicked(int rowIndex, JSONObject row, boolean isRightClick) {
                if (isJobRow(row)) {
                    JSONObject job = row.get("job").isObject();
                    int jobId = (int) job.get("id").isNumber().doubleValue();
                    hostDetailListener.onJobSelected(jobId);
                } else {
                    String resultsPath = Utils.jsonToString(row.get("execution_path"));
                    Utils.openUrlInNewWindow(Utils.getRetrieveLogsUrl(resultsPath));
                }
            }

            public void onTableRefreshed() {}
        });
        tableDecorator.addPaginators();
        selectionManager = tableDecorator.addSelectionManager(false);
        selectionManager.setSelectableRowFilter(this);
        jobsTable.setWidgetFactory(selectionManager);
        tableDecorator.addTableActionsPanel(this, true);
        tableDecorator.addControl("Show verifies, repairs and cleanups", showSpecialTasks);
        addWidget(tableDecorator, "view_host_jobs_table");

        showSpecialTasks.addClickHandler(new ClickHandler() {
            public void onClick(ClickEvent event) {
                jobsTable.setSpecialTasksEnabled(showSpecialTasks.getValue());
                jobsTable.refresh();
            }
        });

        lockButton.addClickHandler(new ClickHandler() {
            public void onClick(ClickEvent event) {
               boolean locked = currentHostObject.get("locked").isBoolean().booleanValue();
               changeLock(!locked);
            }
        });
        addWidget(lockButton, "view_host_lock_button");

        HorizontalPanel host_buttons = new HorizontalPanel();

        reverifyButton.addClickHandler(new ClickHandler() {
            public void onClick(ClickEvent event) {
                JSONObject params = new JSONObject();

                params.put("id", currentHostObject.get("id"));
                AfeUtils.callReverify(params, new SimpleCallback() {
                    public void doCallback(Object source) {
                       refresh();
                    }
                }, "Host " + hostname);
            }
        });
        host_buttons.add(reverifyButton);

        reinstallButton.addClickHandler(new ClickHandler() {
            public void onClick(ClickEvent event) {
                Set<JSONObject> set = new JSONObjectSet<JSONObject>();
                set.add(currentHostObject);
                AfeUtils.scheduleReinstall(set, hostname, jobCreateListener);
            }
        });
        host_buttons.add(reinstallButton);

        HorizontalPanel reservation_buttons = new HorizontalPanel();

        reserveButton.addClickHandler(new ClickHandler() {
            public void onClick(ClickEvent event) {
                JSONArray hostIds = new JSONArray();
                hostIds.set(0, currentHostObject.get("id"));
                AfeUtils.handleHostsReservations(hostIds, true, false, "Host reserved", new SimpleCallback() {
                    public void doCallback(Object source) {
                        refresh();
                    }
                });
            }
        });
        reserveButton.setVisible(false);
        reservation_buttons.add(reserveButton);

        releaseButton.addClickHandler(new ClickHandler() {
            public void onClick(ClickEvent event) {
                JSONArray hostIds = new JSONArray();
                hostIds.set(0, currentHostObject.get("id"));
                AfeUtils.handleHostsReservations(hostIds, false, false, "Host released", new SimpleCallback() {
                    public void doCallback(Object source) {
                        refresh();
                    }
                });
            }
        });

        releaseButton.setVisible(false);
        reservation_buttons.add(releaseButton);

        forceReleaseButton.addClickHandler(new ClickHandler() {
            public void onClick(ClickEvent event) {
                JSONArray hostIds = new JSONArray();
                hostIds.set(0, currentHostObject.get("id"));
                AfeUtils.handleHostsReservations(hostIds, false, true, "Host force released", new SimpleCallback() {
                    public void doCallback(Object source) {
                        refresh();
                    }
                });
            }
        });
        forceReleaseButton.setVisible(false);
        reservation_buttons.add(forceReleaseButton);

        addWidget(host_buttons, "view_host_buttons");
        addWidget(reservation_buttons, "view_host_reservation_buttons");
    }

    public void onError(JSONObject errorObject) {
        // RPC handler will display error
    }

    public ContextMenu getActionMenu() {
        ContextMenu menu = new ContextMenu();
        menu.addItem("Abort job entries", new Command() {
            public void execute() {
                abortSelectedQueueEntries();
            }
        });
        return menu;
    }

    private void abortSelectedQueueEntries() {
        AfeUtils.abortHostQueueEntries(selectionManager.getSelectedObjects(), new SimpleCallback() {
            public void doCallback(Object source) {
                refresh();
            }
        });
    }

    private void updateLockButton() {
        boolean locked = currentHostObject.get("locked").isBoolean().booleanValue();
        if (locked) {
            lockButton.setText("Unlock");
        } else {
            lockButton.setText("Lock");
        }
    }

    private void changeLock(final boolean lock) {
        JSONArray hostIds = new JSONArray();
        hostIds.set(0, currentHostObject.get("id"));

        AfeUtils.changeHostLocks(hostIds, lock, "Host " + hostname, new SimpleCallback() {
            public void doCallback(Object source) {
                refresh();
            }
        });
    }

    private boolean isJobRow(JSONObject row) {
        String type = Utils.jsonToString(row.get("type"));
        return type.equals("Job");
    }

    public boolean isRowSelectable(JSONObject row) {
        return isJobRow(row);
    }
}
