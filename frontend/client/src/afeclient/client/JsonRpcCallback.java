package afeclient.client;

import com.google.gwt.json.client.JSONObject;
import com.google.gwt.json.client.JSONValue;

abstract class JsonRpcCallback {
    public abstract void onSuccess(JSONValue result);
    public void onError(JSONObject errorObject) {
        String name = errorObject.get("name").isString().stringValue();
        String message = errorObject.get("message").isString().stringValue();
        String errorString =  name + ": " + message;
        NotifyManager.getInstance().showError(errorString);
    }
}
