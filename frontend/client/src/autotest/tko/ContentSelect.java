package autotest.tko;

import autotest.common.Utils;
import autotest.common.CustomHistory.HistoryToken;
import autotest.common.ui.SimpleHyperlink;

import com.google.gwt.event.dom.client.ChangeEvent;
import com.google.gwt.event.dom.client.ChangeHandler;
import com.google.gwt.event.dom.client.ClickEvent;
import com.google.gwt.event.dom.client.ClickHandler;
import com.google.gwt.event.logical.shared.HasValueChangeHandlers;
import com.google.gwt.event.logical.shared.ValueChangeEvent;
import com.google.gwt.event.logical.shared.ValueChangeHandler;
import com.google.gwt.event.shared.HandlerRegistration;
import com.google.gwt.json.client.JSONArray;
import com.google.gwt.json.client.JSONObject;
import com.google.gwt.json.client.JSONString;
import com.google.gwt.user.client.ui.Composite;
import com.google.gwt.user.client.ui.ListBox;
import com.google.gwt.user.client.ui.Panel;
import com.google.gwt.user.client.ui.VerticalPanel;

import java.util.ArrayList;
import java.util.Arrays;
import java.util.HashSet;
import java.util.List;
import java.util.Map;
import java.util.Set;

public class ContentSelect extends Composite implements HasValueChangeHandlers<Boolean> {
    
    public static final String HISTORY_OPENED = "_opened";
    
    public static final String ADD_ADDITIONAL_CONTENT = "Add additional content...";
    public static final String CANCEL_ADDITIONAL_CONTENT = "Don't use additional content";
  
    private SimpleHyperlink addLink = new SimpleHyperlink(ADD_ADDITIONAL_CONTENT);
    private ListBox contentSelect = new ListBox(true);
        
    public ContentSelect() {
        Panel panel = new VerticalPanel();
        contentSelect.setVisible(false);
        
        panel.add(addLink);
        panel.add(contentSelect);
        
        initWidget(panel);
        
        addLink.addClickHandler(new ClickHandler() {
            public void onClick(ClickEvent event) {
                if (contentSelect.isVisible()) {
                    addLink.setText(ADD_ADDITIONAL_CONTENT);
                    contentSelect.setVisible(false);
                    notifyHandlers();
                } else {
                    openContentSelect();
                }
            }
        });
        
        contentSelect.addChangeHandler(new ChangeHandler() {
            public void onChange(ChangeEvent event) {
                notifyHandlers();
            }
        });
    }
    
    private void notifyHandlers() {
        ValueChangeEvent.fire(this, hasSelection());
    }
    
    private void openContentSelect() {
        addLink.setText(CANCEL_ADDITIONAL_CONTENT);
        contentSelect.setVisible(true);
        notifyHandlers();
    }
    
    public void addItem(HeaderField field) {
        contentSelect.addItem(field.getName(), field.getSqlName());
    }
    
    public HandlerRegistration addValueChangeHandler(ValueChangeHandler<Boolean> handler) {
        return addHandler(handler, ValueChangeEvent.getType());
    }
    
    public boolean hasSelection() {
        return contentSelect.isVisible() && contentSelect.getSelectedIndex() != -1;
    }
    
    public void addToCondition(JSONObject condition) {
        if (hasSelection()) {
            JSONArray extraInfo = new JSONArray();
            for (int i = 0; i < contentSelect.getItemCount(); i++) {
                if (contentSelect.isItemSelected(i)) {
                    extraInfo.set(extraInfo.size(), new JSONString(contentSelect.getValue(i)));
                }
            }
            condition.put("extra_info", extraInfo);
        }
    }
    
    public void addHistoryArguments(HistoryToken arguments, String name) {
      List<String> fields = new ArrayList<String>();
      for (int i = 0; i < contentSelect.getItemCount(); i++) {
          if (contentSelect.isItemSelected(i)) {
              fields.add(contentSelect.getValue(i));
          }
      }
      String fieldList = Utils.joinStrings(",", fields);
      arguments.put(name, fieldList);
      
      if (contentSelect.isVisible()) {
          arguments.put(name + HISTORY_OPENED, "true");
      }
  }
  
    public void handleHistoryArguments(Map<String, String> arguments, String name) {
        Set<String> fields = new HashSet<String>(Arrays.asList(arguments.get(name).split(",")));
        for (int i = 0; i < contentSelect.getItemCount(); i++) {
            if (fields.contains(contentSelect.getValue(i))) {
                contentSelect.setItemSelected(i, true);
            }
        }
        
        if (arguments.containsKey(name + HISTORY_OPENED)) {
            openContentSelect();
        }
    }
}
