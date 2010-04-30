package autotest.common;

import com.google.gwt.core.client.GWT;
import com.google.gwt.core.client.JavaScriptObject;
import com.google.gwt.core.client.GWT.UncaughtExceptionHandler;
import com.google.gwt.dom.client.Element;
import com.google.gwt.json.client.JSONObject;
import com.google.gwt.user.client.Timer;

import java.util.HashMap;
import java.util.Map;

/**
 * JsonRpcProxy that uses "JSON with Padding" (JSONP) to make requests.  This allows it to get 
 * around the Same-Origin Policy that limits XmlHttpRequest-based techniques.  However, it requires 
 * close coupling with the server and it allows the server to execute arbitrary JavaScript within 
 * the page, so it should only be used with trusted servers.
 * 
 * See http://code.google.com/docreader/#p=google-web-toolkit-doc-1-5&s=google-web-toolkit-doc-1-5&t=Article_UsingGWTForJSONMashups.
 * Much of the code here is borrowed from or inspired by that article.
 */
public class PaddedJsonRpcProxy extends JsonRpcProxy {
    private static final int REQUEST_TIMEOUT_MILLIS = 60000;
    private static final String SCRIPT_TAG_PREFIX = "__jsonp_rpc_script";
    private static final String CALLBACK_PREFIX = "__jsonp_rpc_callback";

    private static int idCounter = 0;

    private String rpcUrl;

    private static class JsonpRequest {
        private int requestId;
        private String requestData;
        private Element scriptTag;
        private String callbackName;
        private Timer timeoutTimer;
        private JsonRpcCallback rpcCallback;
        private boolean timedOut = false;

        public JsonpRequest(String requestData, JsonRpcCallback rpcCallback) {
            requestId = getRequestId();
            this.requestData = requestData;
            this.rpcCallback = rpcCallback;

            callbackName = CALLBACK_PREFIX + requestId;
            addCallback(this, callbackName);

            timeoutTimer = new Timer() {
                @Override
                public void run() {
                    timedOut = true;
                    cleanup();
                    notify.showError("Request timed out");
                    JsonpRequest.this.rpcCallback.onError(null);
                }
            };
        }
        
        private String getFullUrl(String rpcUrl) {
            Map<String, String> arguments = new HashMap<String, String>();
            arguments.put("callback", callbackName);
            arguments.put("request", requestData);
            return rpcUrl + "?" + Utils.encodeUrlArguments(arguments);
        }

        public void send(String rpcUrl) {
            scriptTag = addScript(getFullUrl(rpcUrl), requestId);
            timeoutTimer.schedule(REQUEST_TIMEOUT_MILLIS);
            notify.setLoading(true);
        }

        public void cleanup() {
            dropScript(scriptTag);
            dropCallback(callbackName);
            timeoutTimer.cancel();
            notify.setLoading(false);
        }

        /**
         * This method is called directly from native code (the dynamically loaded <script> calls
         * our callback method, which calls this), so we need to do proper GWT exception handling
         * manually.
         * 
         * See the implementation of com.google.gwt.user.client.Timer.fire(), from which this
         * technique was borrowed.
         */
        @SuppressWarnings("unused")
        public void handleResponse(JavaScriptObject responseJso) {
            UncaughtExceptionHandler handler = GWT.getUncaughtExceptionHandler();
            if (handler == null) {
                handleResponseImpl(responseJso);
                return;
            }

            try {
                handleResponseImpl(responseJso);
            } catch (Throwable throwable) {
                handler.onUncaughtException(throwable);
            }
        }

        public void handleResponseImpl(JavaScriptObject responseJso) {
            cleanup();
            if (timedOut) {
                return;
            }

            JSONObject responseObject = new JSONObject(responseJso);
            handleResponseObject(responseObject, rpcCallback);
        }
    }

    public PaddedJsonRpcProxy(String rpcUrl) {
        this.rpcUrl = rpcUrl;
    }

    private static int getRequestId() {
        return idCounter++;
    }

    private static native void addCallback(JsonpRequest request, String callbackName) /*-{
        window[callbackName] = function(someData) {
            request.@autotest.common.PaddedJsonRpcProxy.JsonpRequest::handleResponse(Lcom/google/gwt/core/client/JavaScriptObject;)(someData);
        }
    }-*/;

    private static native void dropCallback(String callbackName) /*-{
        delete window[callbackName];
    }-*/;

    private static Element addScript(String url, int requestId) {
        String scriptId = SCRIPT_TAG_PREFIX + requestId;
        Element scriptElement = addScriptToDocument(scriptId, url);
        return scriptElement;
    }

    private static native Element addScriptToDocument(String uniqueId, String url) /*-{
        var elem = document.createElement("script");
        elem.setAttribute("language", "JavaScript");
        elem.setAttribute("src", url);
        elem.setAttribute("id", uniqueId);
        document.getElementsByTagName("body")[0].appendChild(elem);
        return elem;
    }-*/;

    private static native void dropScript(Element scriptElement) /*-{
        document.getElementsByTagName("body")[0].removeChild(scriptElement);
    }-*/;

    @Override
    protected void sendRequest(JSONObject request, JsonRpcCallback callback) {
        JsonpRequest jsonpRequest = new JsonpRequest(request.toString(), callback);
        jsonpRequest.send(rpcUrl);
    }
}
