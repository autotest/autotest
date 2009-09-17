package autotest.tko;

import autotest.common.CustomHistory;
import autotest.common.JSONArrayList;
import autotest.common.JsonRpcCallback;
import autotest.common.JsonRpcProxy;
import autotest.common.StaticDataRepository;
import autotest.common.CustomHistory.CustomHistoryListener;
import autotest.common.CustomHistory.HistoryToken;
import autotest.common.ui.NotifyManager;

import com.google.gwt.event.dom.client.ChangeEvent;
import com.google.gwt.event.dom.client.ChangeHandler;
import com.google.gwt.event.dom.client.ClickEvent;
import com.google.gwt.event.dom.client.ClickHandler;
import com.google.gwt.json.client.JSONArray;
import com.google.gwt.json.client.JSONNumber;
import com.google.gwt.json.client.JSONObject;
import com.google.gwt.json.client.JSONString;
import com.google.gwt.json.client.JSONValue;
import com.google.gwt.user.client.History;
import com.google.gwt.user.client.ui.Button;
import com.google.gwt.user.client.ui.Composite;
import com.google.gwt.user.client.ui.DialogBox;
import com.google.gwt.user.client.ui.HorizontalPanel;
import com.google.gwt.user.client.ui.Label;
import com.google.gwt.user.client.ui.ListBox;
import com.google.gwt.user.client.ui.Panel;
import com.google.gwt.user.client.ui.TextBox;
import com.google.gwt.user.client.ui.VerticalPanel;
import com.google.gwt.user.client.ui.Widget;

import java.util.Map;

class SavedQueriesControl extends Composite 
                          implements ChangeHandler, ClickHandler, CustomHistoryListener {
    public static final String HISTORY_TOKEN = "saved_query";
    
    private static final String ADD_QUERY = "Save current...";
    private static final String DELETE_QUERY = "Delete query...";
    private static final String DEFAULT_ITEM = "Saved queries...";
    
    private static JsonRpcProxy rpcProxy = JsonRpcProxy.getProxy();
    private static NotifyManager notifyManager = NotifyManager.getInstance();
    
    private ListBox queryList = new ListBox();
    private QueryActionDialog<TextBox> addQueryDialog;
    private QueryActionDialog<ListBox> deleteQueryDialog;
    
    private static class QueryActionDialog<T extends Widget> extends DialogBox {
        public T widget;
        public Button actionButton, cancelButton;
        
        public QueryActionDialog(T widget, String widgetString, String actionString) {
            super(false, true);
            this.widget = widget;
            Panel dialogPanel = new VerticalPanel();
            Panel widgetPanel = new HorizontalPanel();
            widgetPanel.add(new Label(widgetString));
            widgetPanel.add(widget);
            dialogPanel.add(widgetPanel);
            
            Panel buttonPanel = new HorizontalPanel();
            actionButton = new Button(actionString);
            cancelButton = new Button("Cancel");
            buttonPanel.add(actionButton);
            buttonPanel.add(cancelButton);
            dialogPanel.add(buttonPanel);
            add(dialogPanel);
            
            cancelButton.addClickHandler(new ClickHandler() {
                public void onClick(ClickEvent event) {
                    hide();
                }
            });
        }
    }
    
    public SavedQueriesControl() {
        queryList.addChangeHandler(this);
        populateMainList();
        initWidget(queryList);
        
        addQueryDialog = new QueryActionDialog<TextBox>(new TextBox(),
                                                        "Enter query name:", "Save query");
        addQueryDialog.actionButton.addClickHandler(this);
        deleteQueryDialog = new QueryActionDialog<ListBox>(new ListBox(),
                                                           "Select query:", "Delete query");
        deleteQueryDialog.actionButton.addClickHandler(this);
        
        CustomHistory.addHistoryListener(this);
    }
    
    private void populateMainList() {
        queryList.clear();
        queryList.addItem(DEFAULT_ITEM);
        queryList.addItem(ADD_QUERY);
        queryList.addItem(DELETE_QUERY);
        fillQueryList(queryList);
    }

    private void fillQueryList(final ListBox list) {
        StaticDataRepository staticData = StaticDataRepository.getRepository();
        JSONObject args = new JSONObject();
        args.put("owner", new JSONString(staticData.getCurrentUserLogin()));
        rpcProxy.rpcCall("get_saved_queries", args, new JsonRpcCallback() {
            @Override
            public void onSuccess(JSONValue result) {
                for (JSONObject query : new JSONArrayList<JSONObject>(result.isArray())) {
                    int id = (int) query.get("id").isNumber().doubleValue();
                    list.addItem(query.get("name").isString().stringValue(), 
                                 Integer.toString(id));
                }
            }
        });
    }
    
    @Override
    public void onChange(ChangeEvent event) {
        int selected = queryList.getSelectedIndex();
        queryList.setSelectedIndex(0); // set it back to the default
        
        String queryName = queryList.getItemText(selected);
        if (queryName.equals(DEFAULT_ITEM)) {
            return;
        }
        if (queryName.equals(ADD_QUERY)) {
            addQueryDialog.widget.setText("");
            addQueryDialog.center();
            addQueryDialog.widget.setFocus(true);
            return;
        }
        if (queryName.equals(DELETE_QUERY)) {
            deleteQueryDialog.widget.clear();
            fillQueryList(deleteQueryDialog.widget);
            deleteQueryDialog.center();
            return;
        }
        
        String idString = queryList.getValue(selected);
        // don't use CustomHistory, since we want the token to be processed
        History.newItem(HISTORY_TOKEN + "=" + idString);
    }

    public void onClick(ClickEvent event) {
        if (event.getSource() == addQueryDialog.actionButton) {
            addQueryDialog.hide();
            JSONObject args = new JSONObject();
            args.put("name", new JSONString(addQueryDialog.widget.getText()));
            args.put("url_token", new JSONString(CustomHistory.getLastHistoryToken().toString()));
            rpcProxy.rpcCall("add_saved_query", args, new JsonRpcCallback() {
                @Override
                public void onSuccess(JSONValue result) {
                    notifyManager.showMessage("Query saved");
                    populateMainList();
                }
            });
        } else {
            assert event.getSource() == deleteQueryDialog.actionButton;
            deleteQueryDialog.hide();
            String idString = 
                deleteQueryDialog.widget.getValue(deleteQueryDialog.widget.getSelectedIndex());
            JSONObject args = new JSONObject();
            JSONArray ids = new JSONArray();
            ids.set(0, new JSONNumber(Integer.parseInt(idString)));
            args.put("id_list", ids);
            rpcProxy.rpcCall("delete_saved_queries", args, new JsonRpcCallback() {
                @Override
                public void onSuccess(JSONValue result) {
                    notifyManager.showMessage("Query deleted");
                    populateMainList();
                } 
            });
        }
    }

    public void onHistoryChanged(Map<String, String> arguments) {
        final String idString = arguments.get(HISTORY_TOKEN);
        if (idString == null) {
            return;
        }
        
        JSONObject args = new JSONObject();
        args.put("id", new JSONNumber(Integer.parseInt(idString)));
        rpcProxy.rpcCall("get_saved_queries", args, new JsonRpcCallback() {
            @Override
            public void onSuccess(JSONValue result) {
                JSONArray queries = result.isArray();
                if (queries.size() == 0) {
                    notifyManager.showError("No saved query with ID " + idString);
                    return;
                }
                
                assert queries.size() == 1;
                JSONObject query = queries.get(0).isObject();
                int queryId = (int) query.get("id").isNumber().doubleValue();
                String tokenString = query.get("url_token").isString().stringValue();
                HistoryToken token;
                try {
                    token = HistoryToken.fromString(tokenString);
                } catch (IllegalArgumentException exc) {
                    NotifyManager.getInstance().showError("Invalid saved query token " + 
                                                          tokenString);
                    return;
                }

                // since this is happening asynchronously, the history may have changed, so ensure
                // it's set back to what it should be.
                HistoryToken shortToken = new HistoryToken();
                shortToken.put(HISTORY_TOKEN, Integer.toString(queryId));
                CustomHistory.newItem(shortToken);

                CustomHistory.simulateHistoryToken(token);
            }
        });
    }
}
