package afeclient.client;

import com.google.gwt.json.client.JSONArray;
import com.google.gwt.json.client.JSONNumber;
import com.google.gwt.json.client.JSONObject;
import com.google.gwt.json.client.JSONString;
import com.google.gwt.json.client.JSONValue;
import com.google.gwt.user.client.DOM;
import com.google.gwt.user.client.ui.Button;
import com.google.gwt.user.client.ui.ClickListener;
import com.google.gwt.user.client.ui.KeyboardListener;
import com.google.gwt.user.client.ui.RootPanel;
import com.google.gwt.user.client.ui.TextBox;
import com.google.gwt.user.client.ui.Widget;

import java.util.Iterator;
import java.util.Set;

public class JobDetailView extends TabView {
    public static final String NO_URL = "about:blank";
    public static final String NO_JOB = "No job selected";
    public static final String GO_TEXT = "Go";
    public static final String REFRESH_TEXT = "Refresh";
    public static final int NO_JOB_ID = -1;
    
    public String getElementId() {
        return "view_job";
    }
    
    protected JsonRpcProxy rpcProxy = JsonRpcProxy.getProxy();

    protected int jobId = NO_JOB_ID;

    protected RootPanel allJobData;
    
    protected JobHostsTable hostsTable;
    protected TextBox idInput = new TextBox();
    protected Button idFetchButton = new Button(GO_TEXT);
    protected Button abortButton = new Button("Abort job");
    
    protected void showText(String text, String elementId) {
        DOM.setInnerText(RootPanel.get(elementId).getElement(), text);
    }

    protected void showField(JSONObject job, String field, String elementId) {
        JSONString jsonString = job.get(field).isString();
        String value = "";
        if (jsonString != null)
            value = jsonString.stringValue();
        showText(value, elementId);
    }

    public void setJobID(int id) {
        this.jobId = id;
        idInput.setText(Integer.toString(id));
        idFetchButton.setText(REFRESH_TEXT);
        refresh();
    }

    public void resetPage() {
        showText(NO_JOB, "view_title");
        allJobData.setVisible(false);
    }

    public void refresh() {
        pointToResults(NO_URL, NO_URL);
        JSONObject params = new JSONObject();
        params.put("id", new JSONNumber(jobId));
        rpcProxy.rpcCall("get_jobs_summary", params, new JsonRpcCallback() {
            public void onSuccess(JSONValue result) {
                JSONArray resultArray = result.isArray();
                if(resultArray.size() == 0) {
                    NotifyManager.getInstance().showError("No such job found");
                    resetPage();
                    return;
                }
                JSONObject jobObject = resultArray.get(0).isObject();
                String name = jobObject.get("name").isString().stringValue();
                String owner = jobObject.get("owner").isString().stringValue();
                String jobLogsId = jobId + "-" + owner;
                String title = "Job: " + name + " (" + jobLogsId + ")";
                showText(title, "view_title");
                
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
                
                pointToResults(getResultsURL(jobId), getLogsURL(jobLogsId));
                
                allJobData.setVisible(true);
                
                hostsTable.getHosts(jobId);
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
    
    public void fetchById() {
        String id = idInput.getText();
        try {
            setJobID(Integer.parseInt(id));
            updateHistory();
        }
        catch (NumberFormatException exc) {
            String error = "Invalid job ID " + id;
            NotifyManager.getInstance().showError(error);
        }
    }

    public void initialize() {
        allJobData = RootPanel.get("view_data");
        
        resetPage();
        
        RootPanel.get("job_id_fetch_controls").add(idInput);
        RootPanel.get("job_id_fetch_controls").add(idFetchButton);
        idInput.setVisibleLength(5);
        idInput.addKeyboardListener(new KeyboardListener() {
            public void onKeyPress(Widget sender, char keyCode, int modifiers) {
                if (keyCode == (char) KEY_ENTER)
                    fetchById();
            }

            public void onKeyDown(Widget sender, char keyCode, int modifiers) {}
            public void onKeyUp(Widget sender, char keyCode, int modifiers) {}
        });
        idFetchButton.addClickListener(new ClickListener() {
            public void onClick(Widget sender) {
                fetchById();
            }
        });
        idInput.addKeyboardListener(new KeyboardListener() {
            public void onKeyPress(Widget sender, char keyCode, int modifiers) {
                idFetchButton.setText(GO_TEXT);
            }
            public void onKeyDown(Widget sender, char keyCode, int modifiers) {}
            public void onKeyUp(Widget sender, char keyCode, int modifiers) {} 
        });
        
        hostsTable = new JobHostsTable(rpcProxy);
        RootPanel.get("job_hosts_table").add(hostsTable);
        
        abortButton.addClickListener(new ClickListener() {
            public void onClick(Widget sender) {
                abortJob();
            }
        });
        RootPanel.get("view_abort").add(abortButton);
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
        return "/results/" + jobLogsId;
    }
    
    protected void pointToResults(String resultsUrl, String logsUrl) {
        DOM.setElementProperty(DOM.getElementById("results_link"),
                               "href", resultsUrl);
        DOM.setElementProperty(DOM.getElementById("results_iframe"),
                               "src", resultsUrl);
        DOM.setElementProperty(DOM.getElementById("raw_results_link"),
                               "href", logsUrl);
    }
    
    public String getHistoryToken() {
        String token = super.getHistoryToken();
        if (jobId != NO_JOB_ID)
            token += "_" + jobId;
        return token;
    }

    public void handleHistoryToken(String token) {
        int newJobId;
        try {
            newJobId = Integer.parseInt(token);
        }
        catch (NumberFormatException exc) {
            return;
        }
        if (newJobId != jobId)
            setJobID(newJobId);
    }
}
