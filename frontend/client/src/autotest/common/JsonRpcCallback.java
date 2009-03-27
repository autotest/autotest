package autotest.common;

import autotest.common.ui.NotifyManager;

import com.google.gwt.json.client.JSONObject;
import com.google.gwt.json.client.JSONString;
import com.google.gwt.json.client.JSONValue;

/**
 * One of onSuccess() and onError() is guaranteed to be called for every RPC request.
 */
public abstract class JsonRpcCallback {
    /**
     * Called when a request completes successfully.
     * @param result the value returned by the server.
     */
    public abstract void onSuccess(JSONValue result);

    /**
     * Called when any request error occurs
     * @param errorObject the error object returned by the server, containing keys "name", 
     * "message", and "traceback".  This argument may be null in the case where no server response
     * was received at all. 
     */
    public void onError(JSONObject errorObject) {
        if (errorObject == null) {
            return;
        }

        String errorString =  getErrorString(errorObject);
        JSONString tracebackString = errorObject.get("traceback").isString();
        String traceback = null;
        if (tracebackString != null) {
            traceback = tracebackString.stringValue();
        }

        NotifyManager.getInstance().showError(errorString, traceback);
    }
    
    protected String getErrorString(JSONObject errorObject) {
        if (errorObject == null) {
            return "";
        }

        String name = Utils.jsonToString(errorObject.get("name"));
        String message = Utils.jsonToString(errorObject.get("message"));
        return name + ": " + message;
    }
}
