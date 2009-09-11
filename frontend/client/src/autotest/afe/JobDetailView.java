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

import com.google.gwt.event.dom.client.ClickEvent;
import com.google.gwt.event.dom.client.ClickHandler;
import com.google.gwt.http.client.Request;
import com.google.gwt.http.client.RequestBuilder;
import com.google.gwt.http.client.RequestCallback;
import com.google.gwt.http.client.RequestException;
import com.google.gwt.http.client.Response;
import com.google.gwt.json.client.JSONArray;
import com.google.gwt.json.client.JSONBoolean;
import com.google.gwt.json.client.JSONNumber;
import com.google.gwt.json.client.JSONObject;
import com.google.gwt.json.client.JSONString;
import com.google.gwt.json.client.JSONValue;
import com.google.gwt.user.client.Command;
import com.google.gwt.user.client.ui.Button;
import com.google.gwt.user.client.ui.DisclosurePanel;
import com.google.gwt.user.client.ui.HTML;
import com.google.gwt.user.client.ui.Label;
import com.google.gwt.user.client.ui.ScrollPanel;
import com.google.gwt.user.client.ui.Widget;

import java.util.Set;

public class JobDetailView extends DetailView implements TableWidgetFactory, TableActionsListener {
    private static final String[][] JOB_HOSTS_COLUMNS = {
        {DataTable.CLICKABLE_WIDGET_COLUMN, ""}, // selection checkbox 
        {"hostname", "Host"}, {"full_status", "Status"}, 
        {"host_status", "Host Status"}, {"host_locked", "Host Locked"},
        // columns for status log and debug log links
        {DataTable.CLICKABLE_WIDGET_COLUMN, ""}, {DataTable.CLICKABLE_WIDGET_COLUMN, ""}  
    };
    public static final String NO_URL = "about:blank";
    public static final int NO_JOB_ID = -1;
    public static final int HOSTS_PER_PAGE = 30;
    
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
    protected HTML tkoResultsHtml = new HTML();
    protected ScrollPanel tkoResultsScroller = new ScrollPanel(tkoResultsHtml);
    protected JobDetailListener listener;
    private SelectionManager selectionManager;
    
    private Label controlFile = new Label();
    private DisclosurePanel controlFilePanel = new DisclosurePanel("");
    
    public JobDetailView(JobDetailListener listener) {
        this.listener = listener;
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
                    jobObject = Utils.getSingleValueFromArray(result.isArray()).isObject();
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
                
                String header = Utils.jsonToString(jobObject.get("control_type")) + " control file";
                controlFilePanel.getHeaderTextAccessor().setText(header);
                controlFile.setText(Utils.jsonToString(jobObject.get("control_file")));
                
                JSONObject counts = jobObject.get("status_counts").isObject();
                String countString = AfeUtils.formatStatusCounts(counts, ", ");
                showText(countString, "view_status");
                abortButton.setVisible(isAnyEntryAbortable(counts));
                
                String jobTag = AfeUtils.getJobTag(jobObject);
                pointToResults(getResultsURL(jobId), getLogsURL(jobTag), 
                               getOldResultsUrl(jobId), getTriageUrl(jobId));
                
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
            public void onRowClicked(int rowIndex, JSONObject row) {
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
        
        tkoResultsScroller.setStyleName("results-frame");
        addWidget(tkoResultsScroller, "tko_results");
        
        controlFile.addStyleName("code");
        controlFilePanel.setContent(controlFile);
        addWidget(controlFilePanel, "view_control_file");
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
                String sql = "(status = 'Failed' OR aborted = TRUE)";
                
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
    
    private String getOldResultsUrl(int jobId) {
        return "/tko/compose_query.cgi?" +
               "columns=test&rows=hostname&condition=tag%7E%27" + 
               Integer.toString(jobId) + "-%25%27&title=Report";
    }
    
    private String getTriageUrl(int jobId) {
        return "/new_tko/#tab_id=table_view&columns=Test+name%252CStatus%252CCount+in+group%252C" +
               "Reason&sort=test_name%252Cstatus%252Creason&condition=job_tag+LIKE+%2527" + jobId +
               "-%2525%2527+AND+status+%253C%253E+%2527GOOD%2527&show_invalid=false";
    }
    
    /**
     * Get the path for a job's raw result files.
     * @param jobLogsId id-owner, e.g. "172-showard"
     */
    protected String getLogsURL(String jobLogsId) {
        return Utils.getRetrieveLogsUrl(jobLogsId);
    }
    
    protected void pointToResults(String resultsUrl, String logsUrl,
                                  String oldResultsUrl, String triageUrl) {
        getElementById("results_link").setAttribute("href", resultsUrl);
        getElementById("old_results_link").setAttribute("href", oldResultsUrl);
        getElementById("raw_results_link").setAttribute("href", logsUrl);
        getElementById("triage_failures_link").setAttribute("href", triageUrl);
        if (resultsUrl.equals(NO_URL)) {
            tkoResultsHtml.setHTML("");
            return;
        }

        RequestBuilder requestBuilder =
            new RequestBuilder(RequestBuilder.GET, oldResultsUrl + "&brief=1");
        try {
            requestBuilder.sendRequest("", new RequestCallback() {
                public void onError(Request request, Throwable exception) {
                    tkoResultsHtml.setHTML("");
                    NotifyManager.getInstance().showError(
                        exception.getLocalizedMessage());
                }
                public void onResponseReceived(Request request,
                                               Response response) {
                    tkoResultsHtml.setHTML(response.getText());
                }
            });
        } catch (RequestException ex) {
          NotifyManager.getInstance().showError(ex.getLocalizedMessage());
        }
    }
    
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
        if (jobId == NO_JOB_ID)
            return NO_OBJECT;
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
    
    public Widget createWidget(int row, int cell, JSONObject hostQueueEntry) {
        if (cell == 0) {
            return selectionManager.createWidget(row, cell, hostQueueEntry);
        }

        String executionSubdir = Utils.jsonToString(hostQueueEntry.get("execution_subdir"));
        if (executionSubdir.equals("")) {
            // when executionSubdir == "", it's a job that hasn't yet run.
            return null;
        }

        JSONObject jobObject = hostQueueEntry.get("job").isObject();
        String owner = Utils.jsonToString(jobObject.get("owner"));
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
