package autotest.common;


import com.google.gwt.http.client.Request;
import com.google.gwt.http.client.RequestBuilder;
import com.google.gwt.http.client.RequestCallback;
import com.google.gwt.http.client.RequestException;
import com.google.gwt.http.client.Response;
import com.google.gwt.json.client.JSONException;
import com.google.gwt.json.client.JSONObject;
import com.google.gwt.json.client.JSONParser;
import com.google.gwt.json.client.JSONValue;


/**
 * JsonRpcProxy that uses XmlHttpRequests to make requests to the server.  This is the standard 
 * technique for AJAX and suffers from the usual restrictions -- Same-Origin Policy and a maximum of
 * two simultaneous outstanding requests.
 */
class XhrJsonRpcProxy extends JsonRpcProxy {
    protected RequestBuilder requestBuilder;
    
    public XhrJsonRpcProxy(String url) {
        requestBuilder = new RequestBuilder(RequestBuilder.POST, url);
    }

    @Override
    protected void sendRequest(JSONObject request, final JsonRpcCallback callback) {
        try {
          requestBuilder.sendRequest(request.toString(), new RpcHandler(callback));
        }
        catch (RequestException e) {
            notify.showError("Unable to connect to server");
            callback.onError(null);
            return;
        }

        notify.setLoading(true);
    }

    private static class RpcHandler implements RequestCallback {
        private JsonRpcCallback callback;

        public RpcHandler(JsonRpcCallback callback) {
            this.callback = callback;
        }

        public void onError(Request request, Throwable exception) {
            notify.setLoading(false);
            notify.showError("Unable to make RPC call", exception.toString());
            callback.onError(null);
        }

        public void onResponseReceived(Request request, Response response) {
            notify.setLoading(false);

            String responseText = response.getText();
            int statusCode = response.getStatusCode();
            if (statusCode != 200) {
                notify.showError("Received error " + Integer.toString(statusCode) + " " +
                                 response.getStatusText(),
                                 response.getHeadersAsString() + "\n\n" + responseText);
                callback.onError(null);
                return;
            }

            handleResponseText(responseText, callback);
        }
    }

    private static void handleResponseText(String responseText, JsonRpcCallback callback) {
        JSONValue responseValue = null;
        try {
            responseValue = JSONParser.parse(responseText);
        }
        catch (JSONException exc) {
            JsonRpcProxy.notify.showError(exc.toString(), responseText);
            callback.onError(null);
            return;
        }
    
        JSONObject responseObject = responseValue.isObject();
        handleResponseObject(responseObject, callback);
    }
}
