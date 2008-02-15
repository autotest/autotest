package afeclient.client;

import com.google.gwt.json.client.JSONArray;
import com.google.gwt.json.client.JSONException;
import com.google.gwt.json.client.JSONNull;
import com.google.gwt.json.client.JSONNumber;
import com.google.gwt.json.client.JSONObject;
import com.google.gwt.json.client.JSONParser;
import com.google.gwt.json.client.JSONString;
import com.google.gwt.json.client.JSONValue;
import com.google.gwt.user.client.HTTPRequest;
import com.google.gwt.user.client.ResponseTextHandler;

import java.util.Iterator;
import java.util.Set;

/**
 * A singleton class to facilitate RPC calls to the server.
 */
public class JsonRpcProxy {
    public static final JsonRpcProxy theInstance = new JsonRpcProxy();
    
    protected NotifyManager notify = NotifyManager.getInstance();
    
    protected String url;
    
    // singleton
    private JsonRpcProxy() {}
    
    public static JsonRpcProxy getProxy() {
        return theInstance;
    }
    
    /**
     * Set the URL to which requests are sent.
     */
    public void setUrl(String url) {
        this.url = url;
    }

    protected JSONArray processParams(JSONObject params) {
        JSONArray result = new JSONArray();
        JSONObject newParams = new JSONObject();
        if (params != null) {
            Set keys = params.keySet();
            for (Iterator i = keys.iterator(); i.hasNext(); ) {
                String key = (String) i.next();
                if (params.get(key) != JSONNull.getInstance())
                    newParams.put(key, params.get(key));
            }
        }
        result.set(0, newParams);
        return result;
    }

    /**
     * Make an RPC call.
     * @param method name of the method to call
     * @param params dictionary of parameters to pass
     * @param callback callback to be notified of RPC call results
     * @return true if the call was successfully initiated
     */
    public boolean rpcCall(String method, JSONObject params,
                           final JsonRpcCallback callback) {
        //GWT.log("RPC " + method, null);
        //GWT.log("args: " + params, null);
        JSONObject request = new JSONObject();
        request.put("method", new JSONString(method));
        request.put("params", processParams(params));
        request.put("id", new JSONNumber(0));
        
        notify.setLoading(true);

        boolean success = HTTPRequest.asyncPost(url, 
                                                request.toString(),
                                                new ResponseTextHandler() {
            public void onCompletion(String responseText) {
                //GWT.log("Response: " + responseText, null);
                
                notify.setLoading(false);
                
                JSONValue responseValue = null;
                try {
                    responseValue = JSONParser.parse(responseText);
                }
                catch (JSONException exc) {
                    notify.showError(exc.toString());
                    return;
                }
                
                JSONObject responseObject = responseValue.isObject();
                JSONObject error = responseObject.get("error").isObject();
                if (error != null) {
                    callback.onError(error);
                    return;
                }

                JSONValue result = responseObject.get("result");
                callback.onSuccess(result);

                // Element error_iframe =
                // DOM.getElementById("error_iframe");
                // DOM.setInnerHTML(error_iframe,
                // responseText);
                }
            });
        return success;
    }
}
