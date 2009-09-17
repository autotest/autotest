package autotest.tko;

import autotest.common.ui.SimpleHyperlink;

import com.google.gwt.event.dom.client.ChangeEvent;
import com.google.gwt.event.dom.client.ChangeHandler;
import com.google.gwt.event.dom.client.ClickEvent;
import com.google.gwt.event.dom.client.ClickHandler;
import com.google.gwt.event.logical.shared.CloseEvent;
import com.google.gwt.event.logical.shared.CloseHandler;
import com.google.gwt.event.logical.shared.OpenEvent;
import com.google.gwt.event.logical.shared.OpenHandler;
import com.google.gwt.user.client.DOM;
import com.google.gwt.user.client.Window;
import com.google.gwt.user.client.ui.Button;
import com.google.gwt.user.client.ui.Composite;
import com.google.gwt.user.client.ui.DisclosurePanel;
import com.google.gwt.user.client.ui.HorizontalPanel;
import com.google.gwt.user.client.ui.Panel;
import com.google.gwt.user.client.ui.TextArea;

import java.util.ArrayList;
import java.util.Map;

// TODO(showard): combine this code with similar code from autotest.afe.CreateJobView
public class FilterStringViewer extends Composite {
    
    public static final String VIEW_FILTER_STRING = "View Filter String";
    public static final String HIDE_FILTER_STRING = "Hide Filter String";
    public static final String EDIT_FILTER_STRING = "Edit Filter String";
    public static final String UNEDIT_FILTER_STRING = "Revert Filter String";
    
    public static interface EditListener {
        public void onEdit();
        public void onRevert();
    }
    
    private SimpleHyperlink view = new SimpleHyperlink(VIEW_FILTER_STRING);
    private Button edit = new Button(EDIT_FILTER_STRING);
    private TextArea queries = new TextArea();
    private DisclosurePanel queriesPanel = new DisclosurePanel();
    private boolean filterEdited = false;
    private boolean viewerEditable = false;
    private ArrayList<EditListener> listeners = new ArrayList<EditListener>();
    
    public FilterStringViewer() {
        edit.addClickHandler(new ClickHandler() {
            public void onClick(ClickEvent event) {
                changeEditable(true);
            }
        });
        
        queries.setSize("35em", "10em");
        queries.setReadOnly(true);
        queries.addChangeHandler(new ChangeHandler() {
            public void onChange(ChangeEvent event) {
                filterEdited = true;
            }
        });
        
        Panel viewerHeaderPanel = new HorizontalPanel();
        viewerHeaderPanel.add(view);
        viewerHeaderPanel.add(edit);
        
        queriesPanel.setHeader(viewerHeaderPanel);
        queriesPanel.add(queries);
        
        queriesPanel.addCloseHandler(new CloseHandler<DisclosurePanel>() {
            public void onClose(CloseEvent<DisclosurePanel> e) {
                view.setText(VIEW_FILTER_STRING);
            }
        });
        queriesPanel.addOpenHandler(new OpenHandler<DisclosurePanel>() {
            public void onOpen(OpenEvent<DisclosurePanel> e) {
                view.setText(HIDE_FILTER_STRING);
            }
        });
        
        initWidget(queriesPanel);
    }
    
    public void setText(String text) {
        queries.setText(text);
    }
    
    public String getText() {
        return queries.getText();
    }
    
    public void addEditListener(EditListener listener) {
        listeners.add(listener);
    }
    
    protected void addToHistory(Map<String, String> args, String prefix) {
        args.put(prefix + "_viewerOpen", String.valueOf(queriesPanel.isOpen()));
        args.put(prefix + "_viewerEditable", String.valueOf(viewerEditable));
        if (viewerEditable) {
            args.put(prefix + "_viewerEdited", String.valueOf(filterEdited));
            if (filterEdited) {
                args.put(prefix + "_viewerText", queries.getText());
            }
        }
    }
    
    protected void handleHistoryArguments(Map<String, String> args, String prefix) {
        // No _viewerOpen parameter. This is a preconfig without a specified custom filter.
        if (args.get(prefix + "_viewerOpen") == null) {
            queriesPanel.setOpen(false);
            if (viewerEditable) {
                changeEditable(false);
            }
            return;
        }
        
        queriesPanel.setOpen(Boolean.parseBoolean(args.get(prefix + "_viewerOpen")));
        if (viewerEditable) {
            changeEditable(false);
        }
        if (Boolean.parseBoolean(args.get(prefix + "_viewerEditable"))) {
            changeEditable(false);
            filterEdited = Boolean.parseBoolean(args.get(prefix + "_viewerEdited"));
            if (filterEdited) {
                queries.setText(args.get(prefix + "_viewerText"));
            }
        }
    }
    
    // Change the viewer's editable state
    private void changeEditable(boolean clicked) {
        if (clicked) {
            DOM.eventGetCurrentEvent().cancelBubble(true);
        }
        
        if (viewerEditable) {
            // We only want the confirmation on revert from an edited viewer, and only if "revert"
            // was clicked (not on programmatic revert)
            boolean userCancelled = filterEdited && clicked 
                && !Window.confirm("Are you sure you want to revert your changes?");
            if (userCancelled) {
                return;
            }
            
            viewerEditable = false;
            filterEdited = false;
            queries.setReadOnly(true);
            edit.setText(EDIT_FILTER_STRING);
            for (EditListener listener : listeners) {
                listener.onRevert();
            }
        } else {
            viewerEditable = true;
            queries.setReadOnly(false);
            edit.setText(UNEDIT_FILTER_STRING);
            queriesPanel.setOpen(true);
            for (EditListener listener : listeners) {
                listener.onEdit();
            }
        }
    }
}
