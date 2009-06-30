package autotest.common;

import autotest.common.ui.NotifyManager;

import com.google.gwt.json.client.JSONArray;
import com.google.gwt.json.client.JSONNull;
import com.google.gwt.json.client.JSONNumber;
import com.google.gwt.json.client.JSONObject;
import com.google.gwt.json.client.JSONString;
import com.google.gwt.json.client.JSONValue;

import java.util.HashMap;
import java.util.Map;
import java.util.Set;

public abstract class JsonRpcProxy {
    public static final String AFE_BASE_URL = "/afe/server/";
    public static final String TKO_BASE_URL = "/new_tko/server/";
    private static final String RPC_URL_SUFFIX = "rpc/";
    private static final String JSON_RPC_URL_SUFFIX = "jsonp_rpc/";

    private static String defaultBaseUrl;
    private static final Map<String, JsonRpcProxy> instanceMap =
        new HashMap<String, JsonRpcProxy>();
    protected static final NotifyManager notify = NotifyManager.getInstance();

    public static void setDefaultBaseUrl(String baseUrl) {
        defaultBaseUrl = baseUrl;
    }
    
    public static JsonRpcProxy createProxy(String baseUrl, boolean isPaddedJson) {
        if (isPaddedJson) {
            return new PaddedJsonRpcProxy(baseUrl + JSON_RPC_URL_SUFFIX);
        }
        return new XhrJsonRpcProxy(baseUrl + RPC_URL_SUFFIX);
    }

    public static JsonRpcProxy getProxy(String baseUrl) {
        if (!instanceMap.containsKey(baseUrl)) {
            instanceMap.put(baseUrl, createProxy(baseUrl, false));
        }
        return instanceMap.get(baseUrl);
    }

    public static JsonRpcProxy getProxy() {
        assert defaultBaseUrl != null;
        return getProxy(defaultBaseUrl);
    }
    
    public static void setProxy(String baseUrl, JsonRpcProxy proxy) {
        instanceMap.put(baseUrl, proxy);
    }

    /**
     * Make an RPC call.
     * @param method name of the method to call
     * @param params dictionary of parameters to pass
     * @param callback callback to be notified of RPC call results
     */
    public void rpcCall(String method, JSONObject params, final JsonRpcCallback callback) {
        JSONObject request = buildRequestObject(method, params);
        sendRequest(request, callback);
    }

    protected abstract void sendRequest(JSONObject request, final JsonRpcCallback callback);

    public static JSONObject buildRequestObject(String method, JSONObject params) {
        JSONObject request = new JSONObject();
        request.put("method", new JSONString(method));
        request.put("params", processParams(params));
        request.put("id", new JSONNumber(0));
        return request;
    }

    private static JSONArray processParams(JSONObject params) {
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
    
    protected static void handleResponseObject(JSONObject responseObject, 
                                               JsonRpcCallback callback) {
        JSONValue error = responseObject.get("error");
        if (error == null) {
            notify.showError("Bad JSON response", responseObject.toString());
            callback.onError(null);
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
