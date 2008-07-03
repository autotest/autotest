package autotest.afe;

import autotest.common.table.RpcDataSource;

import com.google.gwt.json.client.JSONArray;
import com.google.gwt.json.client.JSONObject;
import com.google.gwt.json.client.JSONString;
import com.google.gwt.json.client.JSONValue;

import java.util.Arrays;
import java.util.HashMap;
import java.util.List;
import java.util.Map;

/**
 * Custom RpcDataSource to process the list of host queue entries for a job and
 * consolidate metahosts of the same label.
 */
class JobStatusDataSource extends RpcDataSource {
    public JobStatusDataSource() {
        super("get_host_queue_entries", "get_num_host_queue_entries");
    }
    
    @Override
    protected JSONArray handleJsonResult(JSONValue result) {
        JSONArray rows = new JSONArray();
        Map<List<String>, Integer> metaHostCounts = new HashMap<List<String>, Integer>();
        JSONArray queueEntries = result.isArray();
        for(int i = 0; i < queueEntries.size(); i++) {
            JSONObject queueEntry = queueEntries.get(i).isObject();
            JSONValue host = queueEntry.get("host");
            if (host.isNull() != null) {
                // metahost
                incrementMetaHostCount(metaHostCounts, queueEntry);
                continue;
            }
            
            // non-metahost
            processHostData(queueEntry);
            rows.set(rows.size(), queueEntry);
        }
        
        addMetaHostRows(metaHostCounts, rows);
        
        return rows;
    }
    
    protected void processHostData(JSONObject queueEntry) {
        JSONObject host = queueEntry.get("host").isObject();
        queueEntry.put("hostname", host.get("hostname"));
        // don't show host details if the job is complete - it'll only confuse
        // the user
        boolean complete = queueEntry.get("complete").isNumber().doubleValue() > 0;
        if (!complete) {
            queueEntry.put("host_status", host.get("status"));
            queueEntry.put("host_locked", AfeUtils.getLockedText(host));
        }
    }

    protected void incrementMetaHostCount(Map<List<String>, Integer> metaHostCounts, JSONObject queueEntry) {
        String label = queueEntry.get("meta_host").isString().stringValue();
        String status = queueEntry.get("status").isString().stringValue();
        if (status.equals("Queued"))
            status = "Unassigned";
        List<String> key = getMetaHostKey(label, status);
        
        int count = 0;
        if (metaHostCounts.containsKey(key))
            count = metaHostCounts.get(key).intValue();
        metaHostCounts.put(key, Integer.valueOf(count + 1)); 
    }

    private List<String> getMetaHostKey(String label, String status) {
        // arrays don't hash correctly, so use a list instead
        return Arrays.asList(new String[] {label, status});
    }
    
    protected void addMetaHostRows(Map<List<String>, Integer> metaHostCounts, JSONArray rows) {
        for (Map.Entry<List<String>, Integer> entry : metaHostCounts.entrySet()) {
            String label = entry.getKey().get(0), status = entry.getKey().get(1);
            int count = entry.getValue();
            JSONObject row = new JSONObject();
            row.put("hostname", new JSONString(label + " (label)"));
            row.put("status", new JSONString(Integer.toString(count) + 
                                             " " + status));
            rows.set(rows.size(), row);
        }
    }
}