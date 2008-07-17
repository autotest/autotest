package autotest.common;

import autotest.common.ui.NotifyManager;

import com.google.gwt.http.client.Request;
import com.google.gwt.http.client.RequestBuilder;
import com.google.gwt.http.client.RequestCallback;
import com.google.gwt.http.client.RequestException;
import com.google.gwt.http.client.Response;
import com.google.gwt.json.client.JSONArray;
import com.google.gwt.json.client.JSONException;
import com.google.gwt.json.client.JSONNull;
import com.google.gwt.json.client.JSONNumber;
import com.google.gwt.json.client.JSONObject;
import com.google.gwt.json.client.JSONParser;
import com.google.gwt.json.client.JSONString;
import com.google.gwt.json.client.JSONValue;

import java.util.HashMap;
import java.util.Map;
import java.util.Set;

/**
 * A singleton class to facilitate RPC calls to the server.
 */
public class JsonRpcProxy {
    public static final String AFE_URL = "/afe/server/rpc/";
    public static final String TKO_URL = "/new_tko/server/rpc/";
    private static String defaultUrl;
    
    private static final Map<String,JsonRpcProxy> instanceMap = new HashMap<String,JsonRpcProxy>();
    
    protected NotifyManager notify = NotifyManager.getInstance();
    
    protected RequestBuilder requestBuilder;
    
    public static void setDefaultUrl(String url) {
        defaultUrl = url;
    }
    
    public static JsonRpcProxy getProxy(String url) {
        if (!instanceMap.containsKey(url)) {
            instanceMap.put(url, new JsonRpcProxy(url));
        }
        return instanceMap.get(url);
    }
    
    public static JsonRpcProxy getProxy() {
        assert defaultUrl != null;
        return getProxy(defaultUrl);
    }
    
    private JsonRpcProxy(String url) {
        requestBuilder = new RequestBuilder(RequestBuilder.POST, url);
    }

    protected JSONArray processParams(JSONObject params) {
        JSONArray result = new JSONArray();
        JSONObject newParams = new JSONObject();
        if (params != null) {
            Set<String> keys = params.keySet();
            for (String key : keys) {
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
     */
    public void rpcCall(String method, JSONObject params,
                        final JsonRpcCallback callback) {
        JSONObject request = new JSONObject();
        request.put("method", new JSONString(method));
        request.put("params", processParams(params));
        request.put("id", new JSONNumber(0));

        notify.setLoading(true);

        try {
          requestBuilder.sendRequest(request.toString(),
                                     new RpcHandler(callback));
        }
        catch (RequestException e) {
            notify.showError("Unable to connect to server");
        }
    }

    class RpcHandler implements RequestCallback {
        private JsonRpcCallback callback;

        public RpcHandler(JsonRpcCallback callback) {
            this.callback = callback;
        }

        public void onError(Request request, Throwable exception) {
            notify.showError("Unable to make RPC call", exception.toString());
        }

        public void onResponseReceived(Request request, Response response) {
            notify.setLoading(false);

            String responseText = response.getText();
            int statusCode = response.getStatusCode();
            if (statusCode != 200) {
                notify.showError("Received error " +
                                 Integer.toString(statusCode) + " " +
                                 response.getStatusText(),
                                 response.getHeadersAsString() + "\n\n" +
                                 responseText);
                return;
            }

            JSONValue responseValue = null;
            try {
                responseValue = JSONParser.parse(responseText);
            }
            catch (JSONException exc) {
                notify.showError(exc.toString(), responseText);
                return;
            }

            JSONObject responseObject = responseValue.isObject();
            JSONValue error = responseObject.get("error");
            if (error == null) {
                notify.showError("Bad JSON response", responseText);
                return;
            }
            else if (error.isObject() != null) {
                callback.onError(error.isObject());
                return;
            }

            JSONValue result = responseObject.get("result");
            callback.onSuccess(result);
        }
    }
}
