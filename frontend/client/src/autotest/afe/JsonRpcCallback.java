package afeclient.client;

import com.google.gwt.json.client.JSONObject;
import com.google.gwt.json.client.JSONString;
import com.google.gwt.json.client.JSONValue;

public abstract class JsonRpcCallback {
    public abstract void onSuccess(JSONValue result);
    public void onError(JSONObject errorObject) {
        String name = errorObject.get("name").isString().stringValue();
        String message = errorObject.get("message").isString().stringValue();
        JSONString tracebackString = errorObject.get("traceback").isString();
        String traceback = null;
        if (tracebackString != null)
            traceback = tracebackString.stringValue();
        String errorString =  name + ": " + message;
        NotifyManager.getInstance().showError(errorString, traceback);
    }
}
