package autotest.tko;

import autotest.common.JsonRpcCallback;
import autotest.common.JsonRpcProxy;
import autotest.common.Utils;
import autotest.tko.TableView.TableSwitchListener;

import com.google.gwt.core.client.GWT;
import com.google.gwt.core.client.JavaScriptObject;
import com.google.gwt.core.client.GWT.UncaughtExceptionHandler;
import com.google.gwt.json.client.JSONObject;
import com.google.gwt.json.client.JSONString;
import com.google.gwt.json.client.JSONValue;
import com.google.gwt.user.client.ui.Composite;
import com.google.gwt.user.client.ui.HTML;

abstract class Plot extends Composite {
    private static final String CALLBACK_PREFIX = "__plot_drilldown";

    private static int callbackNameCounter = 0;
    protected final static JsonRpcProxy rpcProxy = JsonRpcProxy.getProxy();

    private String rpcName;
    private HTML plotElement = new HTML();
    protected TableSwitchListener listener;

    private String callbackName;

    private static class DummyRpcCallback extends JsonRpcCallback {
        @Override
        public void onSuccess(JSONValue result) {}
    }

    public Plot(String rpcName) {
        this.rpcName = rpcName;
        this.callbackName = getFreshCallbackName();
        initWidget(plotElement);
    }
    
    private static String getFreshCallbackName() {
        callbackNameCounter++;
        return CALLBACK_PREFIX + callbackNameCounter;
    }

    /**
     * This function is called at initialization time and allows the plot to put native 
     * callbacks in place for drilldown functionality from graphs.
     */
    public native void setDrilldownTrigger() /*-{
        var instance = this;
        var name = this.@autotest.tko.Plot::callbackName;
        $wnd[name] = function(drilldownParams) {
            instance.@autotest.tko.Plot::showDrilldown(Lcom/google/gwt/core/client/JavaScriptObject;)(drilldownParams);
        }
    }-*/;

    /**
     * Get a native JS object that acts as a proxy to this object.  Currently the only exposed
     * method is refresh(params), where params is a JS object.  This is only necessary for allowing
     * externally-written native code to use this object without having to write out the full JSNI
     * method call syntax.
     */
    public native JavaScriptObject getNativeProxy() /*-{
        var instance = this;
        return {
            refresh: function(params) {
                jsonObjectParams = @com.google.gwt.json.client.JSONObject::new(Lcom/google/gwt/core/client/JavaScriptObject;)(params);
                instance.@autotest.tko.Plot::refresh(Lcom/google/gwt/json/client/JSONObject;)(jsonObjectParams);
            }
        };
    }-*/;

    @SuppressWarnings("unused") // called from native code (see setDrilldownTrigger)
    private void showDrilldown(JavaScriptObject drilldownParamsJso) {
        UncaughtExceptionHandler handler = GWT.getUncaughtExceptionHandler();
        if (handler == null) {
            showDrilldownImpl(new JSONObject(drilldownParamsJso));
            return;
        }

        try {
            showDrilldownImpl(new JSONObject(drilldownParamsJso));
        } catch (Throwable throwable) {
            handler.onUncaughtException(throwable);
        }
    }

    protected abstract void showDrilldownImpl(JSONObject drilldownParams);

    public void refresh(JSONObject params, final JsonRpcCallback callback) {
        params.put("drilldown_callback", new JSONString(callbackName));
        rpcProxy.rpcCall(rpcName, params, new JsonRpcCallback() {
            @Override
            public void onSuccess(JSONValue result) {
                plotElement.setHTML(Utils.jsonToString(result));
                callback.onSuccess(result);
            }

            @Override
            public void onError(JSONObject errorObject) {
                callback.onError(errorObject);
            }
        });
    }

    public void refresh(JSONObject params) {
        refresh(params, new DummyRpcCallback());
    }

    public void setListener(TableSwitchListener listener) {
        this.listener = listener;
    }
}
