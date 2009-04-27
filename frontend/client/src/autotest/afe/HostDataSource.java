package autotest.afe;

import com.google.gwt.json.client.JSONArray;
import com.google.gwt.json.client.JSONObject;
import com.google.gwt.json.client.JSONString;
import com.google.gwt.json.client.JSONValue;

import autotest.common.JSONArrayList;
import autotest.common.Utils;
import autotest.common.table.RpcDataSource;

public class HostDataSource extends RpcDataSource {
    protected static final String LOCKED_TEXT = "locked_text";
    protected static final String OTHER_LABELS = "other_labels";
    protected static final String HOST_ACLS = "host_acls";
    
    public HostDataSource() {
        super("get_hosts", "get_num_hosts");
    }

    @Override
    protected JSONArray handleJsonResult(JSONValue result) {
        JSONArray hosts = super.handleJsonResult(result);
        for (int i = 0; i < hosts.size(); i++) {
            processHost(hosts.get(i).isObject());
        }
        return hosts;
    }

    protected void processHost(JSONObject host) {
        host.put(LOCKED_TEXT, AfeUtils.getLockedText(host));
        
        JSONString jsonPlatform = host.get("platform").isString();
        String platform = "";
        if (jsonPlatform != null)
            platform = jsonPlatform.stringValue();
        JSONArray labels = host.get("labels").isArray();
        String labelString = "";
        for (int i = 0; i < labels.size(); i++) {
            String label = labels.get(i).isString().stringValue();
            if (label.equals(platform))
                continue;
            if (!labelString.equals(""))
                labelString += ", ";
            labelString += label;
        }
        host.put(OTHER_LABELS, new JSONString(labelString));
        
        JSONArrayList<JSONString> aclsList = 
            new JSONArrayList<JSONString>(host.get("acls").isArray());
        String aclString = Utils.joinStrings(",", aclsList);
        host.put(HOST_ACLS, new JSONString(aclString));
    }
    
    
}
