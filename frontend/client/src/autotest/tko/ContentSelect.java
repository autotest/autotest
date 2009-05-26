package autotest.tko;

import autotest.common.ui.SimpleHyperlink;

import com.google.gwt.json.client.JSONArray;
import com.google.gwt.json.client.JSONObject;
import com.google.gwt.json.client.JSONString;
import com.google.gwt.user.client.ui.ChangeListener;
import com.google.gwt.user.client.ui.ClickListener;
import com.google.gwt.user.client.ui.Composite;
import com.google.gwt.user.client.ui.ListBox;
import com.google.gwt.user.client.ui.Panel;
import com.google.gwt.user.client.ui.VerticalPanel;
import com.google.gwt.user.client.ui.Widget;

public class ContentSelect extends Composite {
  
    public static final String ADD_ADDITIONAL_CONTENT = "Add additional content...";
    public static final String CANCEL_ADDITIONAL_CONTENT = "Don't use additional content";
  
    private SimpleHyperlink addLink = new SimpleHyperlink(ADD_ADDITIONAL_CONTENT);
    private ListBox contentSelect = new ListBox(true);
    
    private ChangeListener listener;
    
    public ContentSelect() {
        Panel panel = new VerticalPanel();
        contentSelect.setVisible(false);
        
        panel.add(addLink);
        panel.add(contentSelect);
        
        initWidget(panel);
        
        addLink.addClickListener(new ClickListener() {
            public void onClick(Widget sender) {
                if (contentSelect.isVisible()) {
                    addLink.setText(ADD_ADDITIONAL_CONTENT);
                    contentSelect.setVisible(false);
                    notifyListener();
                } else {
                    addLink.setText(CANCEL_ADDITIONAL_CONTENT);
                    contentSelect.setVisible(true);
                    notifyListener();
                }
            }
        });
        
        contentSelect.addChangeListener(new ChangeListener() {
            public void onChange(Widget sender) {
                notifyListener();
            }
        });
    }
    
    private void notifyListener() {
        if (listener != null) {
          listener.onChange(this);
        }
    }
    
    public void addItem(HeaderField field) {
        contentSelect.addItem(field.getName(), field.getSqlName());
    }
    
    public void setChangeListener(ChangeListener listener) {
        this.listener = listener;
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
}
