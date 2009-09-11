package autotest.tko;

import autotest.common.CustomHistory;
import autotest.common.JsonRpcCallback;
import autotest.common.JsonRpcProxy;
import autotest.common.Utils;
import autotest.common.CustomHistory.CustomHistoryListener;
import autotest.common.CustomHistory.HistoryToken;
import autotest.common.ui.NotifyManager;
import autotest.common.ui.SimpleDialog;
import autotest.common.ui.SimpleHyperlink;
import autotest.tko.TableView.TableSwitchListener;

import com.google.gwt.event.dom.client.ClickEvent;
import com.google.gwt.event.dom.client.ClickHandler;
import com.google.gwt.json.client.JSONNumber;
import com.google.gwt.json.client.JSONObject;
import com.google.gwt.json.client.JSONString;
import com.google.gwt.json.client.JSONValue;
import com.google.gwt.user.client.Window;
import com.google.gwt.user.client.ui.Composite;
import com.google.gwt.user.client.ui.FlexTable;
import com.google.gwt.user.client.ui.HasVerticalAlignment;
import com.google.gwt.user.client.ui.TextBox;
import com.google.gwt.user.client.ui.Widget;

import java.util.Map;

public abstract class GraphingFrontend extends Composite 
                                       implements CustomHistoryListener, ClickHandler {
    public static final String HISTORY_TOKEN = "embedded_query";
    
    protected FlexTable table = new FlexTable();
    protected JsonRpcProxy rpcProxy = JsonRpcProxy.getProxy();
    protected SimpleHyperlink embeddingLink = new SimpleHyperlink("[Link to this graph]");
    protected TableSwitchListener listener;

    public abstract void refresh();
    public abstract void addToHistory(Map<String, String> args);
    public abstract void handleHistoryArguments(Map<String, String> args);

    /**
     * This function allows subclasses to add parameters to the call to get_embedding_id() RPC,
     * called when a user requests an embeddable link to a graph.
     */
    protected abstract void addAdditionalEmbeddingParams(JSONObject params);
    
    /**
     * @return a short text ID for the frontend
     */
    public abstract String getFrontendId();
    
    protected GraphingFrontend() {
        CustomHistory.addHistoryListener(this);
        embeddingLink.addClickHandler(this);
    }
    
    public void onClick(ClickEvent event) {
        assert event.getSource() == embeddingLink;
        JSONObject params = new JSONObject();
        params.put("url_token", new JSONString(CustomHistory.getLastHistoryToken().toString()));
        addAdditionalEmbeddingParams(params);
        
        rpcProxy.rpcCall("get_embedding_id", params, new JsonRpcCallback() {
            @Override
            public void onSuccess(JSONValue result) {
                String id = Utils.jsonToString(result);
                showEmbeddedGraphHtml(id);
            }
        });
    }

    private void showEmbeddedGraphHtml(String embeddedGraphId) {
        StringBuilder link = new StringBuilder();
        link.append("<a href=\"http://");
        link.append(Window.Location.getHost());
        link.append(Window.Location.getPath());
        link.append("#");
        link.append(HISTORY_TOKEN);
        link.append("=");
        link.append(embeddedGraphId);
        
        link.append("\"><img border=\"0\" src=\"http://");
        link.append(Window.Location.getHost());
        
        link.append(JsonRpcProxy.TKO_BASE_URL);
        link.append("plot/?id=");
        link.append(embeddedGraphId);
        
        link.append("&max_age=10");
        
        link.append("\"></a>");
        
        TextBox linkBox = new TextBox();
        linkBox.setText(link.toString());
        linkBox.setWidth("100%");
        linkBox.setSelectionRange(0, link.length());
        
        new SimpleDialog("Paste HTML to embed in website:", linkBox).center();
    }
    
    protected void setListener(TableSwitchListener listener) {
        this.listener = listener;
    }
    
    protected void addControl(String text, Widget control) {
        int row = TkoUtils.addControlRow(table, text, control);
        table.getFlexCellFormatter().setColSpan(row, 1, 2);
        table.getFlexCellFormatter().setWidth(row, 1, "100%");
        table.getFlexCellFormatter().setVerticalAlignment(row, 0, HasVerticalAlignment.ALIGN_TOP);
    }
    
    // TODO(showard): merge this with the code from SavedQueriesControl
    public void onHistoryChanged(Map<String, String> arguments) {
        final String idString = arguments.get(HISTORY_TOKEN);
        if (idString == null) {
            return;
        }
        
        JSONObject args = new JSONObject();
        args.put("id", new JSONNumber(Integer.parseInt(idString)));
        rpcProxy.rpcCall("get_embedded_query_url_token", args, new JsonRpcCallback() {
            @Override
            public void onSuccess(JSONValue result) {
                String tokenString = Utils.jsonToString(result);
                HistoryToken token;
                try {
                    token = HistoryToken.fromString(tokenString);
                } catch (IllegalArgumentException exc) {
                    NotifyManager.getInstance().showError("Invalid embedded query token " + 
                                                          tokenString);
                    return;
                }

                // since this is happening asynchronously, the history may have changed, so ensure
                // it's set back to what it should be.
                HistoryToken shortToken = new HistoryToken();
                shortToken.put(HISTORY_TOKEN, idString);
                CustomHistory.newItem(shortToken);

                CustomHistory.simulateHistoryToken(token);
            }
        });
    }
}
