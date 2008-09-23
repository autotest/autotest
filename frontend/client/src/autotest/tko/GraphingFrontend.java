package autotest.tko;

import autotest.common.CustomHistory;
import autotest.common.JsonRpcCallback;
import autotest.common.JsonRpcProxy;
import autotest.common.Utils;
import autotest.common.CustomHistory.CustomHistoryListener;
import autotest.common.ui.SimpleHyperlink;
import autotest.tko.TableView.TableSwitchListener;

import com.google.gwt.json.client.JSONNumber;
import com.google.gwt.json.client.JSONObject;
import com.google.gwt.json.client.JSONString;
import com.google.gwt.json.client.JSONValue;
import com.google.gwt.user.client.Window;
import com.google.gwt.user.client.ui.Button;
import com.google.gwt.user.client.ui.ClickListener;
import com.google.gwt.user.client.ui.Composite;
import com.google.gwt.user.client.ui.DialogBox;
import com.google.gwt.user.client.ui.FlexTable;
import com.google.gwt.user.client.ui.HasVerticalAlignment;
import com.google.gwt.user.client.ui.TextBox;
import com.google.gwt.user.client.ui.Widget;

import java.util.Map;

public abstract class GraphingFrontend extends Composite implements CustomHistoryListener {
    
    public static final String HISTORY_TOKEN = "embedded_query";
    
    protected FlexTable table = new FlexTable();
    protected JsonRpcProxy rpcProxy = JsonRpcProxy.getProxy();
    protected SimpleHyperlink embeddingLink = new SimpleHyperlink("[Link to this graph]");
    protected TableSwitchListener listener;

    public abstract void refresh();
    protected abstract void addToHistory(Map<String, String> args);
    protected abstract void handleHistoryArguments(Map<String, String> args);
    protected abstract void setDrilldownTrigger();
    protected abstract void addAdditionalEmbeddingParams(JSONObject params);
    
    protected static class GraphingDialog extends DialogBox {
        protected GraphingDialog(String title, Widget contents) {
            super(false, false);
            
            FlexTable flex = new FlexTable();
            flex.setText(0, 0, title);
            flex.getFlexCellFormatter().setStylePrimaryName(0, 0, "field-name");
            
            flex.setWidget(1, 0, contents);
            
            Button ok = new Button("OK");
            ok.addClickListener(new ClickListener() {
                public void onClick(Widget sender) {
                    hide();
                }
            });
            flex.setWidget(2, 0, ok);
            
            add(flex);
        }
    }
    
    protected void setListener(TableSwitchListener listener) {
        this.listener = listener;
    }
    
    protected void addControl(String text, Widget control) {
        int row = table.getRowCount();
        table.setText(row, 0, text);
        table.getFlexCellFormatter().setStylePrimaryName(row, 0, "field-name");
        table.setWidget(row, 1, control);
        table.getFlexCellFormatter().setColSpan(row, 1, 2);
        table.getFlexCellFormatter().setWidth(row, 1, "100%");
        table.getFlexCellFormatter().setVerticalAlignment(row, 0, HasVerticalAlignment.ALIGN_TOP);
    }
        
    protected GraphingFrontend() {
        CustomHistory.addHistoryListener(this);
        setDrilldownTrigger();
        
        embeddingLink.addClickListener(new ClickListener() {
            public void onClick(Widget sender) {
                JSONObject params = new JSONObject();
                params.put("url_token", new JSONString(CustomHistory.getLastHistoryToken()));
                addAdditionalEmbeddingParams(params);
                
                rpcProxy.rpcCall("get_embedding_id", params, new JsonRpcCallback() {
                    @Override
                    public void onSuccess(JSONValue result) {
                        String id = Utils.jsonToString(result);
                        
                        StringBuilder link = new StringBuilder();
                        link.append("<a href=\"http://");
                        link.append(Window.Location.getHost());
                        link.append(Window.Location.getPath());
                        link.append("#");
                        link.append(HISTORY_TOKEN);
                        link.append("=");
                        link.append(id);
                        
                        link.append("\"><img border=\"0\" src=\"http://");
                        link.append(Window.Location.getHost());
                        
                        link.append(JsonRpcProxy.TKO_BASE_URL);
                        link.append("plot/?id=");
                        link.append(id);
                        
                        link.append("&max_age=10");
                        
                        link.append("\"></a>");
                        
                        TextBox linkBox = new TextBox();
                        linkBox.setText(link.toString());
                        linkBox.setWidth("100%");
                        linkBox.setSelectionRange(0, link.length());
                        
                        new GraphingDialog("Paste HTML to embed in website:", linkBox).center();
                    }
                });
            }
        });
    }
    
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
                String token = Utils.jsonToString(result);

                // since this is happening asynchronously, the history may have changed, so ensure
                // it's set back to what it should be.
                CustomHistory.newItem(HISTORY_TOKEN + "=" + idString);
                CustomHistory.simulateHistoryToken(token);
            }
        });
    }
}
