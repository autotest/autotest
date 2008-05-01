package afeclient.client;

import afeclient.client.table.DynamicTable;
import afeclient.client.table.ListFilter;
import afeclient.client.table.SearchFilter;
import afeclient.client.table.SimpleFilter;
import afeclient.client.table.TableDecorator;
import afeclient.client.table.DynamicTable.DynamicTableListener;

import com.google.gwt.json.client.JSONArray;
import com.google.gwt.json.client.JSONNumber;
import com.google.gwt.json.client.JSONObject;
import com.google.gwt.json.client.JSONValue;
import com.google.gwt.user.client.DOM;
import com.google.gwt.user.client.ui.Button;
import com.google.gwt.user.client.ui.ClickListener;
import com.google.gwt.user.client.ui.RootPanel;
import com.google.gwt.user.client.ui.Widget;
import com.google.gwt.http.client.URL;

import java.util.Iterator;
import java.util.Set;


public class JobDetailView extends DetailView {
    public static final String[][] JOB_HOSTS_COLUMNS = {
        {"hostname", "Host"}, {"status", "Status"}, 
        {"host_status", "Host Status"}, {"host_locked", "Host Locked"}
    };
    public static final String NO_URL = "about:blank";
    public static final int NO_JOB_ID = -1;
    public static final int HOSTS_PER_PAGE = 30;
    
    public interface JobDetailListener {
        public void onHostSelected(String hostname);
    }
    
    protected int jobId = NO_JOB_ID;

    protected DynamicTable hostsTable = new DynamicTable(JOB_HOSTS_COLUMNS, 
                                                         new JobStatusDataSource());
    protected TableDecorator tableDecorator = new TableDecorator(hostsTable);
    protected SimpleFilter jobFilter = new SimpleFilter();
    protected Button abortButton = new Button("Abort job");
    protected Button requeueButton = new Button("Requeue job");
    protected JobDetailListener listener;
    
    public JobDetailView(JobDetailListener listener) {
        this.listener = listener;
    }

    protected void fetchData() {
        pointToResults(NO_URL, NO_URL);
        JSONObject params = new JSONObject();
        params.put("id", new JSONNumber(jobId));
        rpcProxy.rpcCall("get_jobs_summary", params, new JsonRpcCallback() {
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
                String name = jobObject.get("name").isString().stringValue();
                String owner = jobObject.get("owner").isString().stringValue();
                
                showText(name, "view_label");
                showText(owner, "view_owner");
                showField(jobObject, "priority", "view_priority");
                showField(jobObject, "created_on", "view_created");
                showField(jobObject, "control_type", "view_control_type");
                showField(jobObject, "control_file", "view_control_file");
                
                String synchType = jobObject.get("synch_type").isString().stringValue();
                showText(synchType.toLowerCase(), "view_synch_type");
                
                JSONObject counts = jobObject.get("status_counts").isObject();
                String countString = Utils.formatStatusCounts(counts, ", ");
                showText(countString, "view_status");
                abortButton.setVisible(!allFinishedCounts(counts));
                
                String jobLogsId = jobId + "-" + owner;
                pointToResults(getResultsURL(jobId), getLogsURL(jobLogsId));
                
                String title = "Job: " + name + " (" + jobLogsId + ")";
                displayObjectData(title);
                
                jobFilter.setParameter("job", new JSONNumber(jobId));
                hostsTable.refresh();
            }


            public void onError(JSONObject errorObject) {
                super.onError(errorObject);
                resetPage();
            }
        });
    }
    
    protected boolean allFinishedCounts(JSONObject statusCounts) {
        Set keys = statusCounts.keySet();
        for (Iterator i = keys.iterator(); i.hasNext(); ) {
            String key = (String) i.next();
            if (!(key.equals("Completed") || 
                  key.equals("Failed") ||
                  key.equals("Aborting") ||
                  key.equals("Abort") ||
                  key.equals("Aborted") ||
                  key.equals("Stopped")))
                return false;
        }
        return true;
    }
    
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
        tableDecorator.addPaginators();
        addTableFilters();
        RootPanel.get("job_hosts_table").add(tableDecorator);
        
        abortButton.addClickListener(new ClickListener() {
            public void onClick(Widget sender) {
                abortJob();
            }
        });
        RootPanel.get("view_abort").add(abortButton);
        
        requeueButton.addClickListener(new ClickListener() {
            public void onClick(Widget sender) {
                requeueJob();
            } 
        });
        RootPanel.get("view_requeue").add(requeueButton);
    }

    
    protected void addTableFilters() {
        hostsTable.addFilter(jobFilter);
        
        SearchFilter hostnameFilter = new SearchFilter("host__hostname");
        hostnameFilter.setExactMatch(false);
        ListFilter statusFilter = new ListFilter("status");
        StaticDataRepository staticData = StaticDataRepository.getRepository();
        JSONArray statuses = staticData.getData("job_statuses").isArray();
        statusFilter.setChoices(Utils.JSONtoStrings(statuses));
        
        tableDecorator.addFilter("Hostname", hostnameFilter);
        tableDecorator.addFilter("Status", statusFilter);
    }
    
    protected void abortJob() {
        JSONObject params = new JSONObject();
        params.put("id", new JSONNumber(jobId));
        rpcProxy.rpcCall("abort_job", params, new JsonRpcCallback() {
            public void onSuccess(JSONValue result) {
                refresh();
            }
        });
    }
    
    protected void requeueJob() {
        JSONObject params = new JSONObject();
        params.put("id", new JSONNumber(jobId));
        rpcProxy.rpcCall("requeue_job", params, new JsonRpcCallback() {
            public void onSuccess(JSONValue result) {
                int newId = (int) result.isNumber().getValue();
                fetchJob(newId);
            }
        });
    }
    
    protected String getResultsURL(int jobId) {
        return "/tko/compose_query.cgi?" +
               "columns=test&rows=hostname&condition=tag%7E%27" + 
               Integer.toString(jobId) + "-%25%27&title=Report";
    }
    
    /**
     * Get the path for a job's raw result files.
     * @param jobLogsId id-owner, e.g. "172-showard"
     */
    protected String getLogsURL(String jobLogsId) {
	String val = URL.encode("/results/" + jobLogsId);
        return "/tko/retrieve_logs.cgi?job=" + val;
//        return "/tko/retrieve_logs.cgi?job=%2Fresults%2F" + jobLogsId;
    }
    
    protected void pointToResults(String resultsUrl, String logsUrl) {
        DOM.setElementProperty(DOM.getElementById("results_link"),
                               "href", resultsUrl);
        DOM.setElementProperty(DOM.getElementById("results_iframe"),
                               "src", resultsUrl);
        DOM.setElementProperty(DOM.getElementById("raw_results_link"),
                               "href", logsUrl);
    }
    
    protected String getNoObjectText() {
        return "No job selected";
    }
    
    protected String getFetchControlsElementId() {
        return "job_id_fetch_controls";
    }
    
    protected String getDataElementId() {
        return "view_data";
    }
    
    protected String getTitleElementId() {
        return "view_title";
    }

    protected String getObjectId() {
        if (jobId == NO_JOB_ID)
            return NO_OBJECT;
        return Integer.toString(jobId);
    }
    
    public String getElementId() {
        return "view_job";
    }

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
    
    public void fetchJob(int jobId) {
        fetchById(Integer.toString(jobId));
    }
}
