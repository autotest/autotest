package autotest.tko;

import autotest.common.JsonRpcProxy;
import autotest.common.Utils;
import autotest.common.CustomHistory.HistoryToken;
import autotest.tko.TableView.TableSwitchListener;
import autotest.tko.TableView.TableViewConfig;

import com.google.gwt.core.client.EntryPoint;
import com.google.gwt.core.client.GWT;
import com.google.gwt.core.client.JavaScriptObject;
import com.google.gwt.core.client.GWT.UncaughtExceptionHandler;
import com.google.gwt.dom.client.Element;

public class EmbeddedTkoClient implements EntryPoint, TableSwitchListener {
    private String autotestServerUrl; 
    private TestDetailView testDetailView; // we'll use this to generate history tokens

    public void onModuleLoad() {
        JsonRpcProxy.setDefaultBaseUrl(JsonRpcProxy.TKO_BASE_URL);
        testDetailView = new TestDetailView();
        injectNativeMethods();
    }

    /**
     * Creates a global object named Autotest with the following methods.  This objects acts as the
     * entry point for externally-written native code to create embeddable widgets.
     * * initialize(autoservServerUrl) -- must call this before anything else, passing in the URL
     *   to the Autotest server (i.e. "http://myhost").
     * * createMetricsPlot(parent) -- returns a metrics plot object attached to the given parent 
     *   element.
     */
    private native void injectNativeMethods() /*-{
        var instance = this;
        $wnd.Autotest = {
            initialize: function(autotestServerUrl) {
                instance.@autotest.tko.EmbeddedTkoClient::initialize(Ljava/lang/String;)(autotestServerUrl);
            },

            createMetricsPlot: function(parent) {
                return instance.@autotest.tko.EmbeddedTkoClient::createMetricsPlot(Lcom/google/gwt/dom/client/Element;)(parent);
            }
        }
    }-*/;

    @SuppressWarnings("unused") // called from native
    private void initialize(String autotestServerUrl) {
        this.autotestServerUrl = autotestServerUrl;
        JsonRpcProxy proxy = JsonRpcProxy.createProxy(autotestServerUrl + JsonRpcProxy.TKO_BASE_URL,
                                                      true);
        JsonRpcProxy.setProxy(JsonRpcProxy.TKO_BASE_URL, proxy);
    }

    @SuppressWarnings("unused") // called from native
    private JavaScriptObject createMetricsPlot(Element parent) {
        UncaughtExceptionHandler handler = GWT.getUncaughtExceptionHandler();
        if (handler == null) {
            return doCreateMetricsPlot(parent);
        }

        try {
            return doCreateMetricsPlot(parent);
        } catch (Throwable throwable) {
            handler.onUncaughtException(throwable);
            return null;
        }
    }

    private JavaScriptObject doCreateMetricsPlot(Element parent) {
        if (parent == null) {
            throw new IllegalArgumentException("parent element cannot be null");
        }
        Plot plot = new MetricsPlot();
        plot.setDrilldownTrigger();
        plot.setListener(this);
        parent.appendChild(plot.getElement());
        return plot.getNativeProxy();
    }

    public HistoryToken getSelectTestHistoryToken(int testId) {
        testDetailView.updateObjectId(Integer.toString(testId));
        return testDetailView.getHistoryArguments();
    }

    public void onSelectTest(int testId) {
        String fullUrl = autotestServerUrl + "/new_tko/#" + getSelectTestHistoryToken(testId);
        Utils.openUrlInNewWindow(fullUrl);
    }

    public void onSwitchToTable(TableViewConfig config) {
        throw new UnsupportedOperationException();
    }
}
