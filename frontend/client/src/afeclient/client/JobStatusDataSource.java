package afeclient.client;

import afeclient.client.table.RpcDataSource;

import com.google.gwt.json.client.JSONArray;
import com.google.gwt.json.client.JSONObject;
import com.google.gwt.json.client.JSONString;
import com.google.gwt.json.client.JSONValue;

import java.util.Iterator;
import java.util.Set;

/**
 * Custom RpcDataSource to process the dictionary returned by the server 
 * into an array.
 * TODO - just make the server return an array
 */
class JobStatusDataSource extends RpcDataSource {
    public JobStatusDataSource(String getDataMethod, 
                               String getCountMethod) {
        super(getDataMethod, getCountMethod);
    }
    
    protected JSONArray handleJsonResult(JSONValue result) {
        JSONArray array = new JSONArray();
        JSONObject resultObj = result.isObject();
        Set hostnames = resultObj.keySet();
        int count = 0;
        for(Iterator i = hostnames.iterator(); i.hasNext(); count++) {
            String host = (String) i.next();
            JSONObject hostData = resultObj.get(host).isObject();
            String status = hostData.get("status").isString().stringValue();
            JSONValue metaCountValue = hostData.get("meta_count");
            if (metaCountValue.isNull() == null) {
                int metaCount = (int) metaCountValue.isNumber().getValue();
                host += " (label)";
                status = Integer.toString(metaCount) + " unassigned";
            }
            
            JSONObject entryObject = new JSONObject();
            entryObject.put("hostname", new JSONString(host));
            entryObject.put("status", new JSONString(status));
            array.set(count, entryObject);
        }
        
        return array;
    }
}