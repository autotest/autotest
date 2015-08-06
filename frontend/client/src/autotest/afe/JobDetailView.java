package autotest.afe;

import autotest.common.JsonRpcCallback;
import autotest.common.SimpleCallback;
import autotest.common.StaticDataRepository;
import autotest.common.Utils;
import autotest.common.table.DataTable;
import autotest.common.table.DynamicTable;
import autotest.common.table.ListFilter;
import autotest.common.table.SearchFilter;
import autotest.common.table.SelectionManager;
import autotest.common.table.SimpleFilter;
import autotest.common.table.TableDecorator;
import autotest.common.table.DataTable.TableWidgetFactory;
import autotest.common.table.DynamicTable.DynamicTableListener;
import autotest.common.ui.ContextMenu;
import autotest.common.ui.DetailView;
import autotest.common.ui.NotifyManager;
import autotest.common.ui.TableActionsPanel.TableActionsListener;

import com.google.gwt.dom.client.Element;
import com.google.gwt.event.dom.client.ClickEvent;
import com.google.gwt.event.dom.client.ClickHandler;
import com.google.gwt.json.client.JSONArray;
import com.google.gwt.json.client.JSONBoolean;
import com.google.gwt.json.client.JSONNumber;
import com.google.gwt.json.client.JSONObject;
import com.google.gwt.json.client.JSONString;
import com.google.gwt.json.client.JSONValue;
import com.google.gwt.user.client.Command;
import com.google.gwt.user.client.ui.Button;
import com.google.gwt.user.client.ui.DisclosurePanel;
import com.google.gwt.user.client.ui.Frame;
import com.google.gwt.user.client.ui.HTML;
import com.google.gwt.user.client.ui.Label;
import com.google.gwt.user.client.ui.Widget;

import java.util.Set;

public class JobDetailView extends DetailView implements TableWidgetFactory, TableActionsListener {
    private static final String[][] JOB_HOSTS_COLUMNS = {
        {DataTable.CLICKABLE_WIDGET_COLUMN, ""}, // selection checkbox
        {"hostname", "Host"}, {"profile", "Profile"}, {"full_status", "Status"},
        {"host_status", "Host Status"}, {"host_locked", "Host Locked"},
        // columns for status log and debug log links
        {DataTable.CLICKABLE_WIDGET_COLUMN, ""}, {DataTable.CLICKABLE_WIDGET_COLUMN, ""}
    };
    public static final String NO_URL = "about:blank";
    public static final int NO_JOB_ID = -1;
    public static final int HOSTS_PER_PAGE = 30;
    public static final String RESULTS_MAX_WIDTH = "700px";
    public static final String RESULTS_MAX_HEIGHT = "500px";

    public interface JobDetailListener {
        public void onHostSelected(String hostname);
        public void onCloneJob(JSONValue result);
        public void onCreateRecurringJob(int id);
    }

    protected int jobId = NO_JOB_ID;

    private JobStatusDataSource jobStatusDataSource = new JobStatusDataSource();
    protected DynamicTable hostsTable = new DynamicTable(JOB_HOSTS_COLUMNS, jobStatusDataSource);
    protected TableDecorator tableDecorator = new TableDecorator(hostsTable);
    protected SimpleFilter jobFilter = new SimpleFilter();
    protected Button abortButton = new Button("Abort job");
    protected Button cloneButton = new Button("Clone job");
    protected Button recurringButton = new Button("Create recurring job");
    protected Frame tkoResultsFrame = new Frame();

    protected JobDetailListener listener;
    private SelectionManager selectionManager;

    private Label controlFile = new Label();
    private DisclosurePanel controlFilePanel = new DisclosurePanel("");

    protected StaticDataRepository staticData = StaticDataRepository.getRepository();

    public JobDetailView(JobDetailListener listener) {
        this.listener = listener;
        setupSpreadsheetListener(Utils.getBaseUrl());
    }

    private native void setupSpreadsheetListener(String baseUrl) /*-{
        var ins = this;
        $wnd.onSpreadsheetLoad = function(event) {
            if (event.origin !== baseUrl) {
                return;
            }
            ins.@autotest.afe.JobDetailView::resizeResultsFrame(Ljava/lang/String;)(event.data);
        }

        // ataching listener unfortunatelly varies bc not everybody follows standard
        if ($wnd.addEventListener) { //W3C
           $wnd.addEventListener("message", $wnd.onSpreadsheetLoad, false);
        } else if ($wnd.attachEvent) { //IE
           $wnd.attachEvent("onmessage", $wnd.onSpreadsheetLoad);
        } else { //last resort
           $wnd["onmessage"] = $wnd.onSpreadsheetLoad;
        }
    }-*/;

    @SuppressWarnings("unused") // called from native
    private void resizeResultsFrame(String message) {
        String[] parts = message.split(" ");
        tkoResultsFrame.setSize(parts[0], parts[1]);
    }

    @Override
    protected void fetchData() {
        pointToResults(NO_URL, NO_URL, NO_URL, NO_URL);
        JSONObject params = new JSONObject();
        params.put("id", new JSONNumber(jobId));
        rpcProxy.rpcCall("get_jobs_summary", params, new JsonRpcCallback() {
            @Override
            public void onSuccess(JSONValue result) {
                JSONObject jobObject;
                try {
                    jobObject = Utils.getSingleObjectFromArray(result.isArray());
                }
                catch (IllegalArgumentException exc) {
                    NotifyManager.getInstance().showError("No such job found");
                    resetPage();
                    return;
                }
                String name = Utils.jsonToString(jobObject.get("name"));
                String runVerify = Utils.jsonToString(jobObject.get("run_verify"));

                showText(name, "view_label");
                showField(jobObject, "owner", "view_owner");
                showField(jobObject, "priority", "view_priority");
                showField(jobObject, "created_on", "view_created");
                showField(jobObject, "timeout", "view_timeout");
                showField(jobObject, "max_runtime_hrs", "view_max_runtime");
                showField(jobObject, "email_list", "view_email_list");
                showText(runVerify, "view_run_verify");
                showField(jobObject, "reboot_before", "view_reboot_before");
                showField(jobObject, "reboot_after", "view_reboot_after");
                showField(jobObject, "parse_failed_repair", "view_parse_failed_repair");
                showField(jobObject, "synch_count", "view_synch_count");
                showField(jobObject, "dependencies", "view_dependencies");

                if (staticData.getData("drone_sets_enabled").isBoolean().booleanValue()) {
                    showField(jobObject, "drone_set", "view_drone_set");
                }

                String header = Utils.jsonToString(jobObject.get("control_type")) + " control file";
                controlFilePanel.getHeaderTextAccessor().setText(header);
                controlFile.setText(Utils.jsonToString(jobObject.get("control_file")));

                JSONObject counts = jobObject.get("status_counts").isObject();
                String countString = AfeUtils.formatStatusCounts(counts, ", ");
                showText(countString, "view_status");
                abortButton.setVisible(isAnyEntryAbortable(counts));

                String jobTag = AfeUtils.getJobTag(jobObject);
                pointToResults(getResultsURL(jobId), getLogsURL(jobTag),
                               getTriageUrl(jobId), getEmbeddedUrl(jobId));

                String jobTitle = "Job: " + name + " (" + jobTag + ")";
                displayObjectData(jobTitle);

                jobFilter.setParameter("job", new JSONNumber(jobId));
                hostsTable.refresh();
            }


            @Override
            public void onError(JSONObject errorObject) {
                super.onError(errorObject);
                resetPage();
            }
        });
    }

    protected boolean isAnyEntryAbortable(JSONObject statusCounts) {
        Set<String> statuses = statusCounts.keySet();
        for (String status : statuses) {
            if (!(status.equals("Completed") ||
                  status.equals("Failed") ||
                  status.equals("Stopped") ||
                  status.startsWith("Aborted"))) {
                return true;
            }
        }
        return false;
    }

    @Override
    public void initialize() {
        super.initialize();

        idInput.setVisibleLength(5);

        hostsTable.setRowsPerPage(HOSTS_PER_PAGE);
        hostsTable.setClickable(true);
        hostsTable.addListener(new DynamicTableListener() {
            public void onRowClicked(int rowIndex, JSONObject row, boolean isRightClick) {
                JSONObject host = row.get("host").isObject();
                String hostname = host.get("hostname").isString().stringValue();
                listener.onHostSelected(hostname);
            }

            public void onTableRefreshed() {}
        });
        hostsTable.setWidgetFactory(this);

        tableDecorator.addPaginators();
        addTableFilters();
        selectionManager = tableDecorator.addSelectionManager(false);
        tableDecorator.addTableActionsPanel(this, true);
        addWidget(tableDecorator, "job_hosts_table");

        abortButton.addClickHandler(new ClickHandler() {
            public void onClick(ClickEvent event) {
                abortJob();
            }
        });
        addWidget(abortButton, "view_abort");

        cloneButton.addClickHandler(new ClickHandler() {
            public void onClick(ClickEvent event) {
                cloneJob();
            }
        });
        addWidget(cloneButton, "view_clone");

        recurringButton.addClickHandler(new ClickHandler() {
            public void onClick(ClickEvent event) {
                createRecurringJob();
            }
        });
        addWidget(recurringButton, "view_recurring");

        tkoResultsFrame.getElement().setAttribute("scrolling", "no");
        addWidget(tkoResultsFrame, "tko_results");

        controlFile.addStyleName("code");
        controlFilePanel.setContent(controlFile);
        addWidget(controlFilePanel, "view_control_file");

        if (!staticData.getData("drone_sets_enabled").isBoolean().booleanValue()) {
            AfeUtils.removeElement("view_drone_set_wrapper");
        }
    }


    protected void addTableFilters() {
        hostsTable.addFilter(jobFilter);

        SearchFilter hostnameFilter = new SearchFilter("host__hostname", true);
        ListFilter statusFilter = new ListFilter("status");
        StaticDataRepository staticData = StaticDataRepository.getRepository();
        JSONArray statuses = staticData.getData("job_statuses").isArray();
        statusFilter.setChoices(Utils.JSONtoStrings(statuses));

        tableDecorator.addFilter("Hostname", hostnameFilter);
        tableDecorator.addFilter("Status", statusFilter);
    }

    private void abortJob() {
        JSONObject params = new JSONObject();
        params.put("job__id", new JSONNumber(jobId));
        AfeUtils.callAbort(params, new SimpleCallback() {
            public void doCallback(Object source) {
                refresh();
            }
        });
    }

    private void abortSelectedHosts() {
        AfeUtils.abortHostQueueEntries(selectionManager.getSelectedObjects(), new SimpleCallback() {
            public void doCallback(Object source) {
                refresh();
            }
        });
    }

    protected void cloneJob() {
        ContextMenu menu = new ContextMenu();
        menu.addItem("Reuse any similar hosts  (default)", new Command() {
            public void execute() {
                cloneJob(false);
            }
        });
        menu.addItem("Reuse same specific hosts", new Command() {
            public void execute() {
                cloneJob(true);
            }
        });
        menu.addItem("Use failed and aborted hosts", new Command() {
            public void execute() {
                JSONObject queueEntryFilterData = new JSONObject();
                String sql = "(status = 'Failed' OR aborted = TRUE OR " +
                             "(host_id IS NULL AND meta_host IS NULL))";

                queueEntryFilterData.put("extra_where", new JSONString(sql));
                cloneJob(true, queueEntryFilterData);
            }
        });

        menu.showAt(cloneButton.getAbsoluteLeft(),
                cloneButton.getAbsoluteTop() + cloneButton.getOffsetHeight());
    }

    private void cloneJobOnSelectedHosts() {
        Set<JSONObject> hostsQueueEntries = selectionManager.getSelectedObjects();
        JSONArray queueEntryIds = new JSONArray();
        for (JSONObject queueEntry : hostsQueueEntries) {
          queueEntryIds.set(queueEntryIds.size(), queueEntry.get("id"));
        }

        JSONObject queueEntryFilterData = new JSONObject();
        queueEntryFilterData.put("id__in", queueEntryIds);
        cloneJob(true, queueEntryFilterData);
    }

    private void cloneJob(boolean preserveMetahosts) {
        cloneJob(preserveMetahosts, new JSONObject());
    }

    private void cloneJob(boolean preserveMetahosts, JSONObject queueEntryFilterData) {
        JSONObject params = new JSONObject();
        params.put("id", new JSONNumber(jobId));
        params.put("preserve_metahosts", JSONBoolean.getInstance(preserveMetahosts));
        params.put("queue_entry_filter_data", queueEntryFilterData);

        rpcProxy.rpcCall("get_info_for_clone", params, new JsonRpcCallback() {
            @Override
            public void onSuccess(JSONValue result) {
                listener.onCloneJob(result);
            }
        });
    }

    private void createRecurringJob() {
        listener.onCreateRecurringJob(jobId);
    }

    private String getResultsURL(int jobId) {
        return "/new_tko/#tab_id=spreadsheet_view&row=hostname&column=test_name&" +
               "condition=afe_job_id+%253d+" + Integer.toString(jobId) + "&" +
               "show_incomplete=true";
    }

    private String getTriageUrl(int jobId) {
        /*
         * Having a hard-coded path like this is very unfortunate, but there's no simple way
         * in the current design to generate this link by code.
         *
         * TODO: Redesign the system so that we can generate these links by code.
         *
         * Idea: Be able to instantiate a TableView object, ask it to set up to triage this job ID,
         *       and then ask it for the history URL.
         */

        return "/new_tko/#tab_id=table_view&columns=test_name%252Cstatus%252Cgroup_count%252C" +
               "reason&sort=test_name%252Cstatus%252Creason&condition=afe_job_id+%253D+" + jobId +
               "+AND+status+%253C%253E+%2527GOOD%2527&show_invalid=false";
    }

    private String getEmbeddedUrl(int jobId) {
        return "/embedded_spreadsheet/EmbeddedSpreadsheetClient.html?afe_job_id=" + jobId;
    }

    /**
     * Get the path for a job's raw result files.
     * @param jobLogsId id-owner, e.g. "172-showard"
     */
    protected String getLogsURL(String jobLogsId) {
        return Utils.getRetrieveLogsUrl(jobLogsId);
    }

    protected void pointToResults(String resultsUrl, String logsUrl,
                                  String triageUrl, String embeddedUrl) {
        getElementById("results_link").setAttribute("href", resultsUrl);
        getElementById("raw_results_link").setAttribute("href", logsUrl);
        getElementById("triage_failures_link").setAttribute("href", triageUrl);

        tkoResultsFrame.setSize(RESULTS_MAX_WIDTH, RESULTS_MAX_HEIGHT);
        if (!resultsUrl.equals(NO_URL)) {
            updateResultsFrame(tkoResultsFrame.getElement(), embeddedUrl);
        }
    }

    private native void updateResultsFrame(Element frame, String embeddedUrl) /*-{
        // Use location.replace() here so that the frame's URL changes don't show up in the browser
        // window's history
        frame.contentWindow.location.replace(embeddedUrl);
    }-*/;

    @Override
    protected String getNoObjectText() {
        return "No job selected";
    }

    @Override
    protected String getFetchControlsElementId() {
        return "job_id_fetch_controls";
    }

    @Override
    protected String getDataElementId() {
        return "view_data";
    }

    @Override
    protected String getTitleElementId() {
        return "view_title";
    }

    @Override
    protected String getObjectId() {
        if (jobId == NO_JOB_ID) {
            return NO_OBJECT;
        }
        return Integer.toString(jobId);
    }

    @Override
    public String getElementId() {
        return "view_job";
    }

    @Override
    protected void setObjectId(String id) {
        int newJobId;
        try {
            newJobId = Integer.parseInt(id);
        }
        catch (NumberFormatException exc) {
            throw new IllegalArgumentException();
        }
        this.jobId = newJobId;
    }

    public Widget createWidget(int row, int cell, JSONObject hostQueueEntry, DataTable.WidgetType type) {
        if (cell == 0) {
            return selectionManager.createWidget(row, cell, hostQueueEntry, type);
        }

        // one-time hosts have # in their name, which needs to be escaped
        String executionSubdir = Utils.escape(Utils.jsonToString(hostQueueEntry.get("execution_subdir")));
        if (executionSubdir.equals("")) {
            // when executionSubdir == "", it's a job that hasn't yet run.
            return null;
        }

        JSONObject jobObject = hostQueueEntry.get("job").isObject();
        String owner = Utils.escape(Utils.jsonToString(jobObject.get("owner")));
        String basePath = jobId + "-" + owner + "/" + executionSubdir + "/";

        if (cell == JOB_HOSTS_COLUMNS.length - 1) {
            return new HTML(getLogsLinkHtml(basePath + "debug", "Debug logs"));
        } else {
            return new HTML(getLogsLinkHtml(basePath + "status.log", "Status log"));
        }
    }

    private String getLogsLinkHtml(String url, String text) {
        url = Utils.getRetrieveLogsUrl(url);
        return "<a target=\"_blank\" href=\"" + url + "\">" + text + "</a>";
    }

    public ContextMenu getActionMenu() {
        ContextMenu menu = new ContextMenu();

        menu.addItem("Abort hosts", new Command() {
            public void execute() {
                abortSelectedHosts();
            }
        });

        menu.addItem("Clone job on selected hosts", new Command() {
            public void execute() {
                cloneJobOnSelectedHosts();
            }
        });

        return menu;
    }
}
